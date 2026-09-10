import requests
import pandas as pd
import json

BASE_URL = "https://bi.pixon.cc"

RAW_COOKIE = "ss-lb=83e84ea044254b14; session=.eJw1UttyokAQ_RWL55iCgRkgbyjeReOFCG6lqGEuQERGh5Eoqfz7ktrNU1d31-k-fU5_aQkvcZ2zWnv586X1VBc0JqWQ2pO2z1lPsuuN1aqnRK8usqpXVL1PXPcoqwpGn7X37_enboRkda69KHljXVZQ7UWjus0saNgpMWzMiYsYdCgHFDOdMUoQsAxMTOSaBnJpCkgK9a7jWoDqxLUtDhlliKYccj01kMmpBUxsM5fYjmsjnrpmt0HH2CGpQU2LuBwbFABLxwQR6LKOfnKrmfzHBqAuJ7XkiRInVnUVXQcO5IgT27YN0zAxdCAiwIAImwbGDHLD-lnY4UpBcMk6TAd80gS-qe7WX60eGLjPWPdo4KNRgfB2KWKn2l8OzlJE87cwui_99nDGZlPV_elYqZve5IODIGGVOGXwuHqnkZoc-LngF2UOBsvxcfEKz8fQ5A5BTZDsV9Xq8lDl6OP6udyP63t75CKO5pvyiHbtxtmpoVc1uef15_kG8DPY23qgl3NbCrrq37eL1UNc0fTttmkIaAehT2E-bmxPL_3QHXnjU5VTUKaveGrJRxV71kemqsmpRdwpLtHZiagfrYEM-HDaDjIR-0s_PlZJcq3Wg1ckTT9oS0Hv93W6EIMghsdZX2Esw2Pf81hN-335cfYdPMzihReKnbcNduPNdBKBoJiNfFPR6PI2W8Sz6Tpv4UoEmQ5c2OncvdZ_sZOLFE1BmewsyITISvZrQ1IrrH6caYa5Zc4_IRrfR8XJ3S6vjyHOJiW6z5pgrX3_BTfw7ao.aqDyzw.3zTjg5rwPMacxu7o6na9ZyV73Ww"


HEADERS = {
    "Cookie": RAW_COOKIE,
    "Referer": f"{BASE_URL}/",
    "Origin": BASE_URL,
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:155.0) Gecko/20100101 Firefox/155.0",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Connection": "keep-alive",
}

# CSRF
csrf = requests.get(f"{BASE_URL}/api/v1/security/csrf_token/", headers=HEADERS).json()["result"]
HEADERS["X-CSRFToken"] = csrf
print("✅ CSRF OK")

APP_LOOKUP = {
    # package id → tên chuẩn
    "Screw Town" : "com.screwtown.puzzle3d",
    "Screw Land" : "com.woodpuzzle.pin3d"  ,
    "Words Out!" : "word.puzzle.letter.out",
}
def pull_dataset(ds_id: int, columns: list, filters: list = None, 
                 time_range: str = "Last 30 days", row_limit: int = 50000,
                 orderby: list = None, where: str = "") -> pd.DataFrame:
    """Pull data thẳng từ dataset ID, không cần qua chart."""
    
    payload = {
        "datasource": {"id": ds_id, "type": "table"},
        "force": False,
        "queries": [{
            "columns": columns,
            "metrics": [],
            "filters": filters or [],
            "time_range": time_range,
            "orderby": orderby or [],
            "row_limit": row_limit,
            "extras": {"having": "", "where": where},
            "applied_time_extras": {},
            "annotation_layers": [],
            "url_params": {},
            "custom_params": {},
            "custom_form_data": {}
        }],
        "result_format": "json",
        "result_type": "full"
    }

    resp = requests.post(
        f"{BASE_URL}/api/v1/chart/data",   # vẫn dùng endpoint này
        headers=HEADERS,
        json=payload
    )
    
    if resp.status_code != 200:
        print("Error:", resp.status_code, resp.text[:300])
        return pd.DataFrame()

    result = resp.json()
    rows = result[0]["data"] if isinstance(result, list) else result["result"][0]["data"]
    df = pd.DataFrame(rows)

    # Fix timestamp → date
    for col in df.columns:
        if "date" in col.lower() and df[col].dtype == float:
            df[col] = pd.to_datetime(df[col], unit="ms").dt.date

    return df

def get_raw_columns(ds_id: int, exclude_types: list = None) -> list:
    """
    Lấy danh sách columns của dataset, 
    tự động loại bỏ computed/expression columns.
    """
    exclude_types = exclude_types or []
    
    resp = requests.get(f"{BASE_URL}/api/v1/dataset/{ds_id}", headers=HEADERS)
    info = resp.json()["result"]
    
    raw_cols = []
    skipped  = []
    
    for col in info["columns"]:
        name       = col["column_name"]
        col_type   = col.get("type", "")
        expression = col.get("expression", "")  # computed nếu có expression
        
        # Bỏ qua nếu:
        # 1. Có expression (computed column)
        # 2. Type nằm trong exclude list
        if expression and expression.strip():
            skipped.append(f"  ⚠️  SKIP computed : {name} → {expression[:60]}")
            continue
        
        if col_type in exclude_types:
            skipped.append(f"  ⚠️  SKIP type     : {name} ({col_type})")
            continue
        
        raw_cols.append(name)
    
    print(f"✅ {len(raw_cols)} raw columns, ⚠️  {len(skipped)} skipped")
    if skipped:
        print("\n".join(skipped))
    
    return raw_cols

def pull_dataset_safe(ds_id: int, 
                      columns: list = None,       # None = tự lấy tất cả raw cols
                      filters: list = None,
                      time_range: str = "Last 30 days",
                      row_limit: int = 50000,
                      orderby: list = None,
                      where: str = "") -> pd.DataFrame:
    """
    Pull dataset, tự động bỏ qua computed columns nếu không chỉ định columns.
    """
    # Nếu không truyền columns → tự lấy raw columns từ schema
    if columns is None:
        columns = get_raw_columns(ds_id)
    
    return pull_dataset(
        ds_id=ds_id,
        columns=columns,
        filters=filters or [],
        time_range=time_range,
        row_limit=row_limit,
        orderby=orderby or [],
        where=where
    )

def list_all_datasets() -> pd.DataFrame:
    """Liệt kê tất cả datasets với id, name, database."""
    
    rows = []
    page = 0
    while True:
        resp = requests.get(
            f"{BASE_URL}/api/v1/dataset/",
            headers=HEADERS,
            params={"q": json.dumps({"page": page, "page_size": 100})}
        ).json()
        
        items = resp.get("result", [])
        if not items:
            break
            
        for item in items:
            rows.append({
                "id"      : item["id"],
                "name"    : item["table_name"],
                "database": item["database"]["database_name"],
                "schema"  : item.get("schema", "")
            })
        page += 1
    
    df = pd.DataFrame(rows).sort_values("name")
    print(df.to_string(index=False))
    return df


def get_dataset_schema(ds_id: int):
    resp = requests.get(f"{BASE_URL}/api/v1/dataset/{ds_id}", headers=HEADERS)
    info = resp.json()["result"]

    cols = [col['column_name'] for col in info["columns"]]
    cols.sort()
    #result = ", ".join(cols)
    #print(f"{info['table_name']} (id={ds_id}), {result}")

    return cols


def inspect_dataset(ds_id: int, columns: list, sample: int = 500) -> None:
    """In unique values của các cột cần filter để biết đúng giá trị."""
    
    df = pull_dataset(
        ds_id=ds_id,
        columns=columns,
        filters=[],
        time_range="No filter",
        row_limit=sample
    )
    
    if df.empty:
        print("❌ Không lấy được data, ", ds_id)
        return
    
    print(f"✅ Sample {len(df)} rows\n")
    for col in columns:
        if col in df.columns:
            uniq = df[col].dropna().unique()
            print(f"  [{col}] ({len(uniq)} unique): {list(uniq[:15])}")
            if len(uniq) > 15:
                print(f"    ... và {len(uniq)-15} giá trị khác")

datasets = {
    # Daily
    70: "daily_stats",

    # Cohort / Retention
    69: "cohort_retention",
    71: "cohort_ltv",
    99: "cohort_churn",
    95: "version_breakdown",
    96: "level_reach_by_retention_day",

    # Level Funnel
    78: "level_full",
    117: "cohort_attempt_percentage",
    86: "level_drop_percentage",
    97: "level_drop_play_time",
    65: "level_drop_last_activities",
    64: "level_drop_event_flow",

    # Economy
    108: "resource_daily_detail",

    # IAA
    91: "iaa_by_placement",

    # IAP
    67: "iap_by_pack_agg",
    68: "iap_pack_repurchase",
    94: "iap_purchase_flow",
    88: "first_purchase_by_level",
    89: "first_purchase_by_retention_day",
}

app_name = "Words Out!"
time_range = "2026-08-01 : 2026-08-31"
for (i, name) in datasets.items():
    cols = get_dataset_schema(i)
    df = pull_dataset(
        ds_id=i,
        columns=["app_id"],
        filters=[],
        time_range="No filter",
        row_limit=10
    )
    app = app_name
    sample = df["app_id"].dropna().iloc[0]

    if sample.startswith("com.") or "." in sample:
        app = APP_LOOKUP.get(app_name) 

    d = pull_dataset_safe(i,
         filters = [
            {"col": "app_id", "op": "in", "val": app},
        ],
        time_range = time_range,
        row_limit = 300000)
    filename = f"../data/{app_name}_{time_range.replace(" : ", "_")}_{name}.csv"
    d.to_csv(filename, index=False)
    print("Written ", filename);
