import os
import re
from pathlib import Path
import pandas as pd
import numpy as np

COLUMN_TRANSLATIONS = {
    "date_notification": "date",
    "date_rapport": "date",
    "jour": "date",
    "zone_de_sante": "health_zone",
    "zone_sante": "health_zone",
    "nom_zone": "health_zone",
    "nom_sante": "health_zone",
    "nom": "health_zone",
    "province": "province",
    "cas_confirmes": "confirmed_cases",
    "cas_suspects": "suspected_cases",
    "deces": "deaths",
    "gueris": "recovered"
}

STATUS_TRANSLATIONS = {
    "oui": "yes", "non": "no", "vrai": "true", "faux": "false",
    "suspect": "suspected", "confirme": "confirmed", "decede": "deceased"
}


def force_nom_first(df: pd.DataFrame) -> pd.DataFrame:
    """
    Guarantees 'nom' is column #1. Strips any duplicate clean-up columns.
    """
    df.columns = [str(c).lower().strip() for c in df.columns]
    
    target_col = None
    for col in df.columns:
        if col in ['nom', 'health_zone', 'zone_sante', 'zone_de_sante', 'nom_zone']:
            target_col = col
            break
            
    if not target_col:
        for col in df.columns:
            if any(k in col for k in ['zone', 'sante', 'health']):
                target_col = col
                break

    if target_col:
        if target_col != 'nom':
            df = df.rename(columns={target_col: 'nom'})
            
        df = df.loc[:, ~df.columns.duplicated()]
        if 'health_zone' in df.columns and 'nom' in df.columns:
            df = df.drop(columns=['health_zone'])

        cols = ['nom'] + [c for c in df.columns if c != 'nom']
        df = df[cols].copy()
        
    return df


def remove_accents(series: pd.Series) -> pd.Series:
    """Standardizes text by stripping French accents and title-casing names."""
    return (series.astype(str)
            .str.normalize('NFKD')
            .str.encode('ascii', errors='ignore')
            .str.decode('utf-8')
            .str.strip()
            .str.title())


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Applies standard data cleaning and normalization to DataFrames."""
    df.columns = df.columns.str.lower().str.strip()
    df = df.rename(columns=COLUMN_TRANSLATIONS)
    
    zone_cols = [c for c in df.columns if 'zone' in c or 'health_zone' in c]
    if zone_cols:
        col = zone_cols[0]
        df[col] = df[col].astype(str).str.replace(r"(?i)zone de sant(e|é)\s*", "", regex=True)
        df[col] = remove_accents(df[col])
    
    prov_cols = [c for c in df.columns if 'province' in c]
    if prov_cols:
        col = prov_cols[0]
        df[col] = remove_accents(df[col])
    
    if 'date' in df.columns:
        df['date'] = df['date'].astype(str).str.replace(r'[\[\]\'"\s]', '', regex=True)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        if zone_cols:
            df = df.sort_values(by=[zone_cols[0], 'date'])
            
    for col in df.columns:
        if df[col].dtype == 'object' and col not in zone_cols and col not in prov_cols:
            cleaned_series = df[col].astype(str).str.lower().str.strip()
            cleaned_series = (cleaned_series.str.normalize('NFKD')
                              .str.encode('ascii', errors='ignore')
                              .str.decode('utf-8'))
            if cleaned_series.isin(STATUS_TRANSLATIONS.keys()).any():
                df[col] = cleaned_series.replace(STATUS_TRANSLATIONS).str.title()
                
    numeric_candidates = ['confirmed_cases', 'suspected_cases', 'deaths', 'recovered', 'cases', 'value']
    for col in df.columns:
        if col in numeric_candidates or df[col].astype(str).str.upper().isin(['ND', 'N/D', 'NULL']).any():
            df[col] = df[col].astype(str).replace(r'(?i)\b(nd|n/d|null|nan)\b', np.nan, regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def load_fixed_matrix(osrm_path: Path, aliases_path: Path) -> pd.DataFrame:
    df = pd.read_csv(osrm_path, index_col=0)
    row_noms = df["nom"].tolist()

    dest_cols = [c for c in df.columns if c != "nom"]
    diag = pd.Series([df.loc[df.index[i], dest_cols[i]] for i in range(len(row_noms))])
    if not (diag == 0).all():
        raise ValueError(
            "Self-distance is not 0 for every zone -- the positional column "
            "mapping assumption is broken, do not trust this rename."
        )

    df.columns = ["nom"] + row_noms

    aliases = pd.read_csv(aliases_path)
    alias_map = dict(zip(aliases["observed_name"], aliases["canonical_nom"]))
    df["nom"] = df["nom"].replace(alias_map)
    df.columns = ["nom"] + [alias_map.get(c, c) for c in df.columns[1:]]
    return df.set_index("nom")


def compute_osrm_nearest_active(osrm_path: Path, aliases_path: Path, sitrep_path: Path, out_path: Path) -> pd.DataFrame:
    """Computes the nearest active-case zone travel times feature."""
    matrix = load_fixed_matrix(osrm_path, aliases_path)
    print("Matrix fixed and verified:", matrix.shape)

    sitrep = pd.read_csv(sitrep_path)
    # Ensure correct format
    sitrep["date"] = pd.to_datetime(sitrep["date"])

    active_by_date = (
        sitrep[sitrep["cumulative_suspected_cases"] > 0]
        .groupby("date")["nom"].apply(list)
    )
    print(f"Dates with at least one active zone: {len(active_by_date)}")

    records = []
    for date, active_zones in active_by_date.items():
        valid_active = [z for z in active_zones if z in matrix.columns]
        skipped = set(active_zones) - set(valid_active)
        if skipped:
            print(f"  !! {date.date()}: active zone(s) not found in matrix, skipped: {skipped}")
        if not valid_active:
            continue
        min_time = matrix[valid_active].min(axis=1)
        for zone, t in min_time.items():
            records.append({"nom": zone, "date": date, "min_minutes_to_active_zone": t})

    result = pd.DataFrame(records)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out_path, index=False)
    print(f"Saved: {out_path}")
    return result


# Rest of the functions stay intact
def join_insp_sitrep_csvs(input_dir: Path | str, output_path: Path | str) -> pd.DataFrame:
    input_dir = Path(input_dir)
    output_path = Path(output_path)

    csv_files = sorted(input_dir.glob("insp_sitrep*.csv"))
    if not csv_files:
        return pd.DataFrame(columns=["nom", "date"])

    frames: list[pd.DataFrame] = []
    for csv_path in csv_files:
        try:
            df = pd.read_csv(csv_path)
            df.columns = df.columns.str.lower().str.strip()

            cols_to_drop = [col for col in df.columns if col in ['unnamed: 0', 'index']]
            if cols_to_drop:
                df = df.drop(columns=cols_to_drop)

            rename_map = {}
            for col in df.columns:
                if col in ['nom', 'zone_sante', 'zone_de_sante', 'nom_zone', 'health_zone']:
                    rename_map[col] = 'nom'
                elif col in ['date', 'jour', 'date_rapport', 'date_notification']:
                    rename_map[col] = 'date'
            
            df = df.rename(columns=rename_map)

            if 'nom' not in df.columns and len(df.columns) > 0:
                df.rename(columns={df.columns[0]: 'nom'}, inplace=True)
            if 'date' not in df.columns and len(df.columns) > 1:
                df.rename(columns={df.columns[1]: 'date'}, inplace=True)

            if 'nom' not in df.columns or 'date' not in df.columns:
                continue

            df['date'] = df['date'].astype(str).str.strip()
            value_columns = [col for col in df.columns if col not in ['nom', 'date']]
            
            if not value_columns:
                df[f"has_data_{csv_path.stem}"] = 1
                value_columns = [f"has_data_{csv_path.stem}"]

            file_metric_prefix = csv_path.stem.split("__")[1] if len(csv_path.stem.split("__")) >= 2 else csv_path.stem

            for col in value_columns:
                if col in ['value', 'cases', 'count', 'valeur', 'nd']:
                    unique_col_name = f"{file_metric_prefix}_{col}" if col == 'nd' else file_metric_prefix
                    df.rename(columns={col: unique_col_name}, inplace=True)

            frames.append(df)
        except Exception as file_err:
            print(f"❌ Failed to parse {csv_path.name}: {file_err}")

    if not frames:
        return pd.DataFrame(columns=["nom", "date"])

    merged = frames[0]
    for i, frame in enumerate(frames[1:], start=1):
        merged = pd.merge(merged, frame, on=["nom", "date"], how="outer", suffixes=('', f'_dup_{i}'))

    merged = force_nom_first(merged)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return merged


def _read_flowminder_frame(csv_path: Path) -> pd.DataFrame | None:
    with csv_path.open("r", encoding="utf-8") as handle:
        first_line = handle.readline().strip().split(",")

    header_row = (
        len(first_line) >= 2
        and first_line[0].strip().lower() in {"nom", "zone_de_sante", "zone_sante", "zone"}
        and first_line[1].strip().lower() in {"value", "inflow", "outflow", "date"}
    )

    if header_row:
        frame = pd.read_csv(csv_path)
    else:
        frame = pd.read_csv(csv_path, header=None)
        if frame.shape[1] < 2:
            return None
        frame = frame.iloc[:, :2].copy()
        frame.columns = ["nom", "value"]

    if frame.shape[1] < 2:
        return None

    frame = frame.iloc[:, :2].copy()
    frame.columns = ["nom", "value"]
    return frame


def join_flowminder_csvs(input_dir: Path | str, output_path: Path | str) -> pd.DataFrame:
    input_dir = Path(input_dir)
    output_path = Path(output_path)

    csv_files = sorted(input_dir.glob("flowminder*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No flowminder*.csv files found.")

    frames: list[pd.DataFrame] = []
    for csv_path in csv_files:
        frame = _read_flowminder_frame(csv_path)
        if frame is None:
            continue
        feature_name = csv_path.stem
        feature_frame = frame[["nom", "value"]].copy()
        feature_frame.rename(columns={"value": feature_name}, inplace=True)
        frames.append(feature_frame)

    merged = frames[0]
    for frame in frames[1:]:
        merged = pd.merge(merged, frame, on="nom", how="outer")

    merged = force_nom_first(merged)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return merged


def join_worldpop_csvs(input_dir: Path | str, output_path: Path | str) -> pd.DataFrame:
    input_dir = Path(input_dir)
    output_path = Path(output_path)

    all_csvs = list(input_dir.glob("*.csv"))
    count_file, density_file = None, None

    for f in all_csvs:
        name_lower = f.name.lower()
        if "density" in name_lower:
            density_file = f
        elif "count" in name_lower:
            count_file = f

    def _extract_metric(file_path: Path, metric_name: str) -> pd.DataFrame:
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.lower().str.strip()
        
        geo_col = None
        for col in df.columns:
            if any(k in col for k in ["zone", "nom", "health", "sante"]):
                geo_col = col
                break
        if not geo_col:
            geo_col = df.columns[0]
            
        val_col = None
        for col in df.columns:
            if col != geo_col and any(k in col for k in ["value", "sum", "pop", "count", "density", "mean"]):
                val_col = col
                break

        if val_col:
            df_clean = df[[geo_col, val_col]].copy()
            df_clean.columns = ["nom", metric_name]
        else:
            df_clean = df[[geo_col]].copy()
            df_clean.columns = ["nom"]
            df_clean[metric_name] = np.nan
        return df_clean

    df_count = _extract_metric(count_file, "count") if count_file else pd.DataFrame(columns=["nom", "count"])
    df_density = _extract_metric(density_file, "density") if density_file else pd.DataFrame(columns=["nom", "density"])

    if not df_count.empty and not df_density.empty:
        merged = pd.merge(df_count, df_density, on="nom", how="outer")
    elif not df_count.empty:
        merged = df_count
    else:
        merged = df_density

    merged = force_nom_first(merged)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    return merged
