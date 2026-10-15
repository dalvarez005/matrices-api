import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import db as database
from . import ocr
from .apk import router as apk_router
from .auth import current_user, issue_token, optional_user, upsert_google_user, verify_google_token
from .config import get_settings
from .db import Operation, User, get_db
from .matrix import MAX_MATRICES, MatrixError, evaluate, normalize

log = logging.getLogger("matrices")

Matrix = list[list[str]]
Operator = Literal["+", "-"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    database.init_db()
    app.state.ocr_slots = asyncio.Semaphore(settings.ocr_max_concurrency)
    log.info("OCR %s", "habilitado" if settings.ocr_enabled and ocr.available() else "deshabilitado")
    yield


app = FastAPI(title="MatriCalc API", version="1.1.0", lifespan=lifespan)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?" if _settings.cors_allow_localhost else None,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(apk_router)


@app.exception_handler(MatrixError)
async def _matrix_error(_: Request, exc: MatrixError):
    return JSONResponse({"detail": str(exc)}, status_code=422)


# ------------------------------------------------------------------ Modelos


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    picture: str | None

    @classmethod
    def of(cls, u: User) -> "UserOut":
        return cls(id=u.id, email=u.email, name=u.name, picture=u.picture)


class GoogleLogin(BaseModel):
    idToken: str = Field(min_length=10)


class SessionOut(BaseModel):
    token: str
    user: UserOut


class CalculateIn(BaseModel):
    """Una expresión A ± B ± C …

    Se envía como [matrices] + [operators] (uno entre cada par), o en la forma
    simple de siempre: [operation] con [a] y [b].
    """

    matrices: list[Matrix] | None = Field(None, min_length=2, max_length=MAX_MATRICES)
    operators: list[Operator] | None = None
    operation: Literal["add", "subtract"] | None = None
    a: Matrix | None = None
    b: Matrix | None = None
    source: Literal["manual", "image"] = "manual"
    # Con sesión se guarda en el historial salvo que se pida lo contrario.
    save: bool = True

    @model_validator(mode="after")
    def _expression(self) -> "CalculateIn":
        if self.matrices is None:
            if self.operation is None or self.a is None or self.b is None:
                raise ValueError("Envía 'matrices' y 'operators', o 'operation' con 'a' y 'b'.")
            self.matrices = [self.a, self.b]
            self.operators = ["+" if self.operation == "add" else "-"]
        elif self.operators is None or len(self.operators) != len(self.matrices) - 1:
            raise ValueError("Debe haber un operador entre cada par de matrices.")
        return self


def operation_name(operators: list[str]) -> str:
    if len(operators) > 1:
        return "compound"
    return "add" if operators[0] == "+" else "subtract"


class OperationOut(BaseModel):
    id: int | None
    operation: str
    matrices: list[Matrix]
    operators: list[Operator]
    # Las dos primeras matrices, para clientes anteriores.
    a: Matrix
    b: Matrix
    result: Matrix
    source: str
    createdAt: datetime | None

    @classmethod
    def of(cls, o: Operation) -> "OperationOut":
        matrices = o.matrices or [o.matrix_a, o.matrix_b]
        operators = o.operators or ["-" if o.operation == "subtract" else "+"]
        return cls(
            id=o.id, operation=o.operation, matrices=matrices, operators=operators,
            a=matrices[0], b=matrices[1], result=o.result, source=o.source,
            createdAt=o.created_at,
        )


class HistoryPage(BaseModel):
    items: list[OperationOut]
    nextBefore: int | None


class OcrMatrix(BaseModel):
    rows: int
    cols: int
    values: list[list[str | None]]


class OcrOut(BaseModel):
    matrices: list[OcrMatrix]
    operation: Literal["add", "subtract"] | None


# ------------------------------------------------------------------- Rutas


@app.get("/health")
def health():
    ok = database.ping()
    body = {"status": "ok" if ok else "unhealthy", "db": ok, "ocr": ocr.available()}
    return JSONResponse(body, status_code=200 if ok else 503)


@app.post("/api/auth/google", response_model=SessionOut)
def login_google(body: GoogleLogin, db: Session = Depends(get_db)):
    info = verify_google_token(body.idToken)
    user = upsert_google_user(db, info)
    return SessionOut(token=issue_token(user), user=UserOut.of(user))


@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return UserOut.of(user)


@app.delete("/api/auth/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Borra la cuenta y todo su historial."""
    db.execute(delete(Operation).where(Operation.user_id == user.id))
    db.delete(user)
    db.commit()


@app.post("/api/calculate", response_model=OperationOut)
def calculate_route(
    body: CalculateIn,
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
):
    matrices = [normalize(m) for m in body.matrices]
    result = evaluate(matrices, body.operators)
    op = Operation(
        operation=operation_name(body.operators),
        matrix_a=matrices[0],
        matrix_b=matrices[1],
        matrices=matrices,
        operators=body.operators,
        result=result,
        source=body.source,
    )
    if user is not None and body.save:
        op.user_id = user.id
        db.add(op)
        db.commit()
    return OperationOut.of(op)


@app.get("/api/history", response_model=HistoryPage)
def history(
    limit: int = Query(20, ge=1, le=100),
    before: int | None = Query(None, description="id del último elemento de la página anterior"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = select(Operation).where(Operation.user_id == user.id)
    if before is not None:
        q = q.where(Operation.id < before)
    rows = db.scalars(q.order_by(Operation.id.desc()).limit(limit + 1)).all()
    items = [OperationOut.of(o) for o in rows[:limit]]
    return HistoryPage(items=items, nextBefore=items[-1].id if len(rows) > limit else None)


@app.delete("/api/history/{op_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_one(op_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    op = db.get(Operation, op_id)
    if op is None or op.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Operación no encontrada.")
    db.delete(op)
    db.commit()


@app.delete("/api/history", status_code=status.HTTP_204_NO_CONTENT)
def delete_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(delete(Operation).where(Operation.user_id == user.id))
    db.commit()


@app.post("/api/ocr", response_model=OcrOut)
async def read_image(request: Request, file: UploadFile):
    settings = get_settings()
    if not settings.ocr_enabled or not ocr.available():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "La lectura de imágenes no está disponible.")
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"La imagen supera {settings.max_upload_mb} MB."
        )
    # En la Orange Pi cada lectura ocupa un núcleo: las demás esperan turno.
    async with request.app.state.ocr_slots:
        try:
            tokens = await run_in_threadpool(ocr.read_tokens, data, settings.ocr_timeout_seconds)
        except ocr.OcrError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    result = ocr.tokens_to_matrices(tokens)
    if not result["matrices"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "No encontré números en la imagen. Prueba con una foto más cerca y con buena luz.",
        )
    return result
