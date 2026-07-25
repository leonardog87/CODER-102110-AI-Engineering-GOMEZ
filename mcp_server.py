"""
mcp_server.py
--------------
Servidor MCP "educativo" para Ciudad Analítica.

Objetivo del módulo:
- Cargar datos estructurados desde CSV.
- Volcar esa información en una base SQLite en memoria.
- Exponer una única función contractual para consultas seguras:
    mcp_execute_query(tabla, filtros, agente_rol)
- Aplicar RBAC (control de acceso por rol).
- Sanitizar resultados sensibles antes de devolverlos.

Este archivo está pensado para ser leído en clase:
- cada paso está comentado,
- los errores se devuelven en formato JSON/Dict,
- se evita exponer detalles internos de la infraestructura.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------------------------
# Configuración básica de logging.
# En una demo educativa ayuda a entender qué ocurrió sin romper la UI.
# -------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ciudad_analitica.mcp_server")


# -------------------------------------------------------------------
# Rutas solicitadas por el enunciado.
# Si los CSV no existen todavía, el módulo usa datos simulados de fallback
# para que la app siga funcionando durante el desarrollo.
# -------------------------------------------------------------------
EMPLEADOS_CSV_PATH = Path(os.getenv("EMPLEADOS_CSV", "raw_data/empleados.csv"))
CLIENTES_CSV_PATH = Path(os.getenv("CLIENTES_CSV", "raw_data/clientes.csv"))

# Tablas permitidas por contrato.
ALLOWED_TABLES = {"empleados", "clientes"}

# Columnas que no deben salir cuando el rol es soporte y consulta clientes.
SENSITIVE_CLIENT_COLUMNS = {
    "Ingreso_Mensual_ARS",
    "Gasto_Mensual_ARS",
    "Telefono",
}

# Conexión global a SQLite en memoria.
# Importante: si cerramos esta conexión, la base desaparece.
_CONN: Optional[sqlite3.Connection] = None


# -------------------------------------------------------------------
# Datos de respaldo para que el módulo sea ejecutable aunque los CSV
# aún no existan en el equipo del alumno.
# -------------------------------------------------------------------
def _sample_empleados() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Empleado_ID": 1,
                "Nombre": "Ana Pérez",
                "Area": "Infraestructura",
                "Rol": "Administrador de Sistemas",
                "Email": "ana.perez@ciudadanalitica.local",
                "Telefono": "555-1001",
                "Salario_ARS": 1850000,
                "Sucursal": "CABA",
            },
            {
                "Empleado_ID": 2,
                "Nombre": "Luis Gómez",
                "Area": "Soporte",
                "Rol": "Técnico Nivel 1",
                "Email": "luis.gomez@ciudadanalitica.local",
                "Telefono": "555-1002",
                "Salario_ARS": 980000,
                "Sucursal": "CABA",
            },
            {
                "Empleado_ID": 3,
                "Nombre": "María Torres",
                "Area": "Seguridad",
                "Rol": "Analista SOC",
                "Email": "maria.torres@ciudadanalitica.local",
                "Telefono": "555-1003",
                "Salario_ARS": 2100000,
                "Sucursal": "Rosario",
            },
        ]
    )


def _sample_clientes() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Cliente_ID": 101,
                "Nombre": "Comercial Andes SA",
                "Segmento": "Enterprise",
                "Estado": "Activo",
                "Ingreso_Mensual_ARS": 24500000,
                "Gasto_Mensual_ARS": 18000000,
                "Telefono": "11-4000-1001",
                "Email": "contacto@andes.com.ar",
                "Pais": "Argentina",
            },
            {
                "Cliente_ID": 102,
                "Nombre": "TechNova SRL",
                "Segmento": "PyME",
                "Estado": "Activo",
                "Ingreso_Mensual_ARS": 7600000,
                "Gasto_Mensual_ARS": 4300000,
                "Telefono": "11-4000-1002",
                "Email": "hola@technova.com.ar",
                "Pais": "Argentina",
            },
            {
                "Cliente_ID": 103,
                "Nombre": "Clínica Sur",
                "Segmento": "Health",
                "Estado": "Inactivo",
                "Ingreso_Mensual_ARS": 13500000,
                "Gasto_Mensual_ARS": 9000000,
                "Telefono": "11-4000-1003",
                "Email": "mesa@clinicasur.com.ar",
                "Pais": "Argentina",
            },
        ]
    )


# -------------------------------------------------------------------
# Utilidades de carga y normalización.
# -------------------------------------------------------------------
def _clean_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia el DataFrame eliminando columnas sin nombre (Unnamed) y normalizando.
    """
    # Eliminar columnas que comienzan con "Unnamed"
    df = df.loc[:, ~df.columns.str.contains('^Unnamed', case=False)]
    
    # Eliminar columnas completamente vacías
    df = df.dropna(axis=1, how='all')
    
    # Eliminar filas completamente vacías
    df = df.dropna(axis=0, how='all')
    
    return df


def _read_csv_with_fallback(path: Path, fallback_df: pd.DataFrame) -> pd.DataFrame:
    """
    Intenta leer un CSV con separador ';' como pide el enunciado.
    """
    try:
        if path.exists():
            df = pd.read_csv(path, sep=";")
            logger.info("CSV cargado correctamente: %s", path)
            # ─── Limpiar columnas Unnamed ───
            df = _clean_dataframe_columns(df)
            return df
        logger.warning("CSV no encontrado en %s. Usando datos simulados.", path)
        return fallback_df.copy()
    except Exception as exc:
        logger.exception("Error leyendo %s. Se usarán datos simulados.", path)
        return fallback_df.copy()


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza valores faltantes para que SQLite los reciba bien."""
    clean_df = df.copy()
    # Limpiar columnas Unnamed primero
    clean_df = _clean_dataframe_columns(clean_df)
    # Convertir NaN/NaT a None para SQLite
    clean_df = clean_df.where(pd.notnull(clean_df), None)
    return clean_df


def _fix_empleados_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reorganiza el DataFrame de empleados para corregir columnas mal ubicadas.
    """
    # Si el DataFrame tiene columnas Unnamed, significa que el CSV estaba mal formado
    unnamed_cols = [col for col in df.columns if col.startswith('Unnamed')]
    
    if unnamed_cols:
        logger.info("🔄 Reorganizando columnas de empleados...")
        
        # Crear un nuevo DataFrame con las columnas correctas
        fixed_data = []
        
        for _, row in df.iterrows():
            # Extraer datos básicos
            nombre = row.get('Nombre', '')
            apellido = row.get('Apellido', '')
            puesto = row.get('Puesto', '')
            mail = row.get('Mail', '')
            telefono = row.get('Telefono', '')
            sueldo = row.get('Sueldo_ARS', '')
            direccion = row.get('Direccion', '')
            
            # Extraer equipo y acceso AWS de las columnas correctas
            equipo = row.get('Equipo', '').strip()
            acceso_aws = row.get('Acceso_AWS', '').strip()
            
            # Si "Equipo" tiene un valor con espacio al inicio, limpiarlo
            if equipo and equipo.startswith(' '):
                equipo = equipo.strip()
            
            # Obtener los valores de las columnas Unnamed
            unnamed_values = [str(row.get(col, '')).strip() for col in unnamed_cols if pd.notna(row.get(col))]
            
            # Si no hay valores en las columnas Unnamed, usar lo que está en Acceso_AWS
            if not unnamed_values and acceso_aws:
                unnamed_values = [acceso_aws]
            
            # Combinar los valores de Unnamed en una sola cadena
            detalle_equipo = ' | '.join([v for v in unnamed_values if v and v != 'nan'])
            
            fixed_row = {
                'Nombre': nombre,
                'Apellido': apellido,
                'Puesto': puesto,
                'Mail': mail,
                'Telefono': telefono,
                'Sueldo_ARS': sueldo,
                'Direccion': direccion,
                'Equipo': equipo,
                'Acceso_AWS': acceso_aws,
                'Detalle': detalle_equipo if detalle_equipo else acceso_aws
            }
            fixed_data.append(fixed_row)
        
        return pd.DataFrame(fixed_data)
    
    return df    


def _df_to_sqlite(conn: sqlite3.Connection, table_name: str, df: pd.DataFrame) -> None:
    """
    Vuelca un DataFrame a SQLite usando pandas.
    Se reemplaza la tabla completa para simplificar el flujo educativo.
    """
    normalized = _normalize_dataframe(df)
    normalized.to_sql(table_name, conn, if_exists="replace", index=False)


def _initialize_database() -> sqlite3.Connection:
    """
    Crea la base en memoria y carga las dos tablas pedidas.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Facilita convertir resultados a dict.

    empleados_df = _read_csv_with_fallback(EMPLEADOS_CSV_PATH, _sample_empleados())
    clientes_df = _read_csv_with_fallback(CLIENTES_CSV_PATH, _sample_clientes())

    _df_to_sqlite(conn, "empleados", empleados_df)
    _df_to_sqlite(conn, "clientes", clientes_df)

    logger.info("Base de datos SQLite en memoria inicializada con éxito.")
    return conn


def get_connection() -> sqlite3.Connection:
    """
    Devuelve la conexión global, inicializándola si todavía no existe.
    """
    global _CONN
    if _CONN is None:
        _CONN = _initialize_database()
    return _CONN


# Inicialización inmediata al importar el módulo.
get_connection()


# -------------------------------------------------------------------
# Serialización segura de resultados.
# -------------------------------------------------------------------
def _rows_to_dicts(rows: Iterable[sqlite3.Row]) -> List[Dict[str, Any]]:
    """
    Convierte filas SQLite a lista de diccionarios nativos de Python.
    """
    return [dict(row) for row in rows]


def _sanitize_client_output(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sanitización tolerante a mayúsculas: elimina columnas sensibles antes de devolver datos.
    Esta es la parte clave de la política de mínimo privilegio.
    """
    sensitive_lower = {col.lower() for col in SENSITIVE_CLIENT_COLUMNS}
    sanitized_rows: List[Dict[str, Any]] = []
    
    for row in rows:
        # Filtramos comparando en minúscula para evitar fugas si el CSV cambió el formato
        sanitized = {k: v for k, v in row.items() if k.lower() not in sensitive_lower}
        sanitized_rows.append(sanitized)
        
    return sanitized_rows


def _build_where_clause(conn: sqlite3.Connection, tabla: str, filtros: Dict[str, Any]) -> tuple[str, List[Any]]:
    """
    Construye un WHERE dinámico inspeccionando las columnas reales de la base de datos.
    Esto evita crasheos si el LLM envía 'Estado' pero la columna en el CSV se llama 'estado',
    y usa LIKE para mejorar la tolerancia en las búsquedas de texto.
    """
    if not filtros:
        return "", []

    # 1. Introspección: Obtenemos cómo se llaman realmente las columnas en la DB
    cursor = conn.execute(f"PRAGMA table_info({tabla})")
    columnas_reales = {row["name"].lower(): row["name"] for row in cursor.fetchall()}

    clauses: List[str] = []
    params: List[Any] = []

    for key, value in filtros.items():
        col_lower = key.lower()
        
        # 2. Solo aplicamos el filtro si la columna existe en la tabla real
        if col_lower in columnas_reales:
            col_exacta = columnas_reales[col_lower]
            
            # 3. Flexibilidad: Si es texto, usamos LIKE para tolerar nombres incompletos
            if isinstance(value, str):
                clauses.append(f"{col_exacta} LIKE ?")
                params.append(f"%{value}%")
            else:
                clauses.append(f"{col_exacta} = ?")
                params.append(value)
        else:
            logger.warning(f"Filtro ignorado: El agente intentó usar una columna inexistente '{key}'.")

    if not clauses:
        return "", []

    return " WHERE " + " AND ".join(clauses), params


# ===================================================================
# FUNCIÓN PRINCIPAL DE AGREGACIÓN CON ESTADÍSTICAS OPCIONALES
# ===================================================================
def _get_aggregated_data(
    conn: sqlite3.Connection, 
    tabla: str, 
    filtros: Dict[str, Any],
    include_stats: bool = False
) -> Dict[str, Any]:
    """
    Devuelve datos agregados en lugar de listas completas.
    
    Args:
        conn: Conexión a SQLite
        tabla: Nombre de la tabla
        filtros: Filtros para la consulta
        include_stats: Si es True, incluye estadísticas financieras (solo para Admin)
    """
    logger.info(f"📊 _get_aggregated_data: tabla={tabla}, filtros={filtros}, include_stats={include_stats}")
    
    try:
        # Verificar que la tabla existe
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabla,))
        if not cursor.fetchone():
            raise ValueError(f"La tabla '{tabla}' no existe en la base de datos")
        
        query_where, params = _build_where_clause(conn, tabla, filtros)
        logger.info(f"📝 WHERE: {query_where}, params={params}")
        
        # ─── CONTAR TOTAL ───
        count_sql = f"SELECT COUNT(*) as total FROM {tabla}{query_where}"
        cursor = conn.execute(count_sql, params)
        row = cursor.fetchone()
        total = row["total"] if row else 0
        logger.info(f"📊 Total encontrado: {total}")
        
        if total == 0:
            return {
                "total": 0,
                "sample": [],
                "stats": {},
                "message": "No se encontraron registros."
            }
        
        # ─── OBTENER MUESTRA CON CAMPOS REDUCIDOS ───
        if tabla == "clientes":
            sample_sql = f"""
                SELECT 
                    Empresa, 
                    Nombre_Responsable, 
                    Apellido_Responsable, 
                    Mail,
                    Pais, 
                    Ciudad, 
                    Servicio_Contratado
                FROM {tabla}{query_where} 
                LIMIT 10
            """
        elif tabla == "empleados":
            sample_sql = f"""
                SELECT 
                    Nombre, 
                    Apellido, 
                    Puesto, 
                    Mail,
                    Equipo
                FROM {tabla}{query_where} 
                LIMIT 10
            """
        else:
            sample_sql = f"SELECT * FROM {tabla}{query_where} LIMIT 10"
        
        cursor = conn.execute(sample_sql, params)
        sample = _rows_to_dicts(cursor.fetchall())
        logger.info(f"📊 Muestra obtenida: {len(sample)} registros")
        
        # ─── CALCULAR ESTADÍSTICAS SOLO SI SE SOLICITA ───
        stats = {}
        if include_stats:
            try:
                if tabla == "clientes":
                    stats_sql = f"""
                        SELECT 
                            SUM(Ingreso_Mensual_ARS) as total_ingresos,
                            AVG(Ingreso_Mensual_ARS) as promedio_ingreso,
                            SUM(Gasto_Mensual_ARS) as total_gastos,
                            AVG(Gasto_Mensual_ARS) as promedio_gasto
                        FROM {tabla}{query_where}
                    """
                    cursor = conn.execute(stats_sql, params)
                    stats_row = cursor.fetchone()
                    if stats_row:
                        stats = dict(stats_row)
                        for key in stats:
                            if stats[key] is not None:
                                stats[key] = round(float(stats[key]), 2)
                        logger.info(f"📊 Estadísticas clientes: {stats}")
                
                elif tabla == "empleados":
                    stats_sql = f"""
                        SELECT 
                            SUM(Sueldo_ARS) as total_sueldos,
                            AVG(Sueldo_ARS) as promedio_sueldo
                        FROM {tabla}{query_where}
                    """
                    cursor = conn.execute(stats_sql, params)
                    stats_row = cursor.fetchone()
                    if stats_row:
                        stats = dict(stats_row)
                        for key in stats:
                            if stats[key] is not None:
                                stats[key] = round(float(stats[key]), 2)
                        logger.info(f"📊 Estadísticas empleados: {stats}")
            except Exception as e:
                logger.warning(f"⚠️ No se pudieron calcular estadísticas: {e}")
        
        return {
            "total": total,
            "sample": sample,
            "stats": stats,
            "message": f"Se encontraron {total} registros. Mostrando muestra de {len(sample)}."
        }
        
    except Exception as e:
        logger.error(f"❌ Error en _get_aggregated_data: {e}")
        import traceback
        traceback.print_exc()
        raise


def _response(
    status_code: int,
    status: str,
    data: Any = None,
    message: str = "",
) -> Dict[str, Any]:
    """
    Envoltorio estándar de respuestas.
    Sirve para que el LLM y la UI sepan interpretar el resultado sin ambigüedad.
    """
    payload = {
        "status_code": status_code,
        "status": status,
        "message": message,
        "data": data,
    }
    return payload


# ===================================================================
# API PRINCIPAL MCP CON RBAC
# ===================================================================
def mcp_execute_query(tabla: str, filtros: dict, agente_rol: str) -> dict:
    """
    Ejecuta una consulta segura con agregación inteligente y RBAC.
    
    Args:
        tabla: "clientes" o "empleados"
        filtros: Diccionario con filtros para la consulta
        agente_rol: "Soporte_Nivel_1" o "Admin_Nivel_2"
    
    Returns:
        Dict con status_code, status, message y data
    """
    try:
        logger.info(f"🔍 [MCP] tabla={tabla}, filtros={filtros}, rol={agente_rol}")
        
        # ─── VALIDACIÓN DE TABLA ───
        if tabla not in ALLOWED_TABLES:
            return _response(
                status_code=400,
                status="bad_request",
                message=f"Tabla inválida. Solo se permiten {', '.join(ALLOWED_TABLES)}.",
                data=[],
            )

        filtros = filtros or {}
        role = str(agente_rol).strip()
        conn = get_connection()

        # ─── RBAC: SOPORTE_NIVEL_1 ───
        if role == "Soporte_Nivel_1":
            logger.info(f"🔍 [MCP] Procesando consulta para Soporte_Nivel_1")
            
            # ❌ Soporte NO puede ver empleados
            if tabla == "empleados":
                return _response(
                    status_code=403,
                    status="forbidden",
                    message="Acceso denegado: el rol Soporte_Nivel_1 no puede consultar empleados.",
                    data=[],
                )

            # ✅ Soporte puede ver clientes PERO SIN estadísticas financieras
            try:
                aggregated = _get_aggregated_data(conn, tabla, filtros, include_stats=False)
                logger.info(f"✅ [MCP] Agregación exitosa: {aggregated.get('total', 0)} registros")
            except Exception as e:
                logger.error(f"❌ [MCP] Error en _get_aggregated_data: {e}")
                import traceback
                traceback.print_exc()
                return _response(
                    status_code=500,
                    status="error",
                    message=f"Error en agregación: {str(e)}",
                    data=[],
                )
            
            # Sanitizar muestra de clientes (eliminar campos sensibles)
            if tabla == "clientes" and "sample" in aggregated:
                try:
                    aggregated["sample"] = _sanitize_client_output(aggregated["sample"])
                    logger.info(f"✅ [MCP] Sanitización de muestra aplicada")
                except Exception as e:
                    logger.error(f"❌ [MCP] Error en sanitización: {e}")
                    return _response(
                        status_code=500,
                        status="error",
                        message=f"Error en sanitización: {str(e)}",
                        data=[],
                    )
            
            return _response(
                status_code=200,
                status="ok",
                message=f"Consulta exitosa. {aggregated['message']}",
                data=aggregated,
            )

        # ─── RBAC: ADMIN_NIVEL_2 ───
        elif role == "Admin_Nivel_2":
            logger.info(f"🔍 [MCP] Procesando consulta para Admin_Nivel_2")
            
            # ✅ Admin puede ver TODO (clientes + estadísticas)
            try:
                aggregated = _get_aggregated_data(conn, tabla, filtros, include_stats=True)
                logger.info(f"✅ [MCP] Agregación exitosa: {aggregated.get('total', 0)} registros")
            except Exception as e:
                logger.error(f"❌ [MCP] Error en _get_aggregated_data: {e}")
                import traceback
                traceback.print_exc()
                return _response(
                    status_code=500,
                    status="error",
                    message=f"Error en agregación: {str(e)}",
                    data=[],
                )
            
            # Sanitizar muestra de clientes (solo para clientes)
            if tabla == "clientes" and "sample" in aggregated:
                try:
                    aggregated["sample"] = _sanitize_client_output(aggregated["sample"])
                except Exception as e:
                    logger.error(f"❌ [MCP] Error en sanitización: {e}")
                    return _response(
                        status_code=500,
                        status="error",
                        message=f"Error en sanitización: {str(e)}",
                        data=[],
                    )
            
            return _response(
                status_code=200,
                status="ok",
                message=f"Consulta exitosa. {aggregated['message']}",
                data=aggregated,
            )

        # ─── ROL DESCONOCIDO ───
        return _response(
            status_code=403,
            status="forbidden",
            message="Rol no autorizado o no reconocido.",
            data=[],
        )

    except sqlite3.Error as exc:
        logger.exception("❌ [MCP] Error interno de SQLite")
        import traceback
        traceback.print_exc()
        return _response(
            status_code=500,
            status="error",
            message=f"Error en la base de datos: {str(exc)}",
            data=[],
        )

    except Exception as exc:
        logger.exception("❌ [MCP] Error inesperado")
        import traceback
        traceback.print_exc()
        return _response(
            status_code=500,
            status="error",
            message=f"Error inesperado: {str(exc)}",
            data=[],
        )


# -------------------------------------------------------------------
# Utilidades opcionales para depuración y observabilidad.
# -------------------------------------------------------------------
def list_tables() -> List[str]:
    """Devuelve las tablas disponibles en la base en memoria."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    )
    return [row["name"] for row in cursor.fetchall()]


def preview_table(table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Vista rápida para depuración local.
    No forma parte del contrato MCP principal, pero ayuda a inspeccionar el estado.
    """
    if table_name not in ALLOWED_TABLES:
        raise ValueError("Tabla inválida para preview.")
    conn = get_connection()
    cursor = conn.execute(f"SELECT * FROM {table_name} LIMIT ?", (int(limit),))
    return _rows_to_dicts(cursor.fetchall())


if __name__ == "__main__":
    # Bloque de prueba mínima para ejecutar el módulo aislado.
    print(json.dumps({"tables": list_tables()}, ensure_ascii=False, indent=2))

    demo_1 = mcp_execute_query(
        tabla="clientes",
        filtros={"Estado": "Activo"},
        agente_rol="Soporte_Nivel_1",
    )
    print("\n=== Demo 1: Soporte_Nivel_1 (clientes activos) ===")
    print(json.dumps(demo_1, ensure_ascii=False, indent=2))

    demo_2 = mcp_execute_query(
        tabla="empleados",
        filtros={"Area": "Infraestructura"},
        agente_rol="Soporte_Nivel_1",
    )
    print("\n=== Demo 2: Soporte_Nivel_1 (empleados infraestructura) ===")
    print(json.dumps(demo_2, ensure_ascii=False, indent=2))
    
    demo_3 = mcp_execute_query(
        tabla="clientes",
        filtros={"Pais": "Argentina"},
        agente_rol="Admin_Nivel_2",
    )
    print("\n=== Demo 3: Admin_Nivel_2 (clientes Argentina) ===")
    print(json.dumps(demo_3, ensure_ascii=False, indent=2))