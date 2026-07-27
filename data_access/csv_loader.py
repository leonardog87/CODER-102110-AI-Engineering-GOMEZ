"""Lectura y validación del archivo empleados.csv."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_access.config import logger

EMPLEADO_COLUMNS = (
    "DNI",
    "Apellido",
    "Nombre",
    "Area",
    "Puesto",
    "Sueldo_ARS",
)


def read_empleados_csv(path: Path) -> pd.DataFrame:
    """Lee empleados.csv y valida que coincida con el esquema esperado."""
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo de empleados: {path}")

    dataframe = pd.read_csv(
        path,
        sep=";",
        encoding="utf-8-sig",
        dtype={"DNI": "string"},
    )
    dataframe.columns = [str(column).strip() for column in dataframe.columns]

    actual_columns = tuple(dataframe.columns)
    if actual_columns != EMPLEADO_COLUMNS:
        raise ValueError(
            "El esquema de empleados.csv no es válido. "
            f"Esperado: {', '.join(EMPLEADO_COLUMNS)}. "
            f"Encontrado: {', '.join(actual_columns)}."
        )

    dataframe = dataframe.dropna(axis=0, how="all").copy()
    if dataframe.empty:
        raise ValueError("empleados.csv no contiene registros.")

    text_columns = ("DNI", "Apellido", "Nombre", "Area", "Puesto")
    for column in text_columns:
        dataframe[column] = dataframe[column].astype("string").str.strip()

    missing = dataframe[list(EMPLEADO_COLUMNS)].isna() | (
        dataframe[list(EMPLEADO_COLUMNS)].astype("string").apply(
            lambda column: column.str.strip().eq("")
        )
    )
    if missing.any(axis=None):
        rows = [str(index + 2) for index in dataframe.index[missing.any(axis=1)]]
        raise ValueError(
            "empleados.csv contiene campos obligatorios vacíos en las líneas: "
            + ", ".join(rows)
        )

    if dataframe["DNI"].duplicated().any():
        duplicated = dataframe.loc[dataframe["DNI"].duplicated(), "DNI"].tolist()
        raise ValueError(f"Hay DNI duplicados en empleados.csv: {duplicated}")

    dataframe["Sueldo_ARS"] = pd.to_numeric(
        dataframe["Sueldo_ARS"],
        errors="raise",
    ).astype("int64")
    if (dataframe["Sueldo_ARS"] < 0).any():
        raise ValueError("Sueldo_ARS no puede contener valores negativos.")

    logger.info(
        "CSV de empleados validado: %s (%s registros).",
        path,
        len(dataframe),
    )
    return dataframe[list(EMPLEADO_COLUMNS)]


def normalize_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Convierte valores faltantes de pandas a valores compatibles con SQLite."""
    return dataframe.where(pd.notnull(dataframe), None)
