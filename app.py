from typing import Optional
from fastapi import FastAPI, Query
import numpy as np
import pandas as pd

app = FastAPI(title="TKK ERP Inventory Management System")

# ----------------------------------------------------
# 1. ส่วนประมวลผลและทำความสะอาดไฟล์ Excel (คำสั่งเดิม)
# ----------------------------------------------------
def load_and_clean_excel(file_path="TKKERP (5).xlsx"):
    try:
        df = pd.read_excel(file_path, sheet_name="Sheet1")
        df_clean = df.iloc[1:].copy()
        df_clean.columns = [
            "โซน",
            "จำนวนคงเหลือ",
            "ยด",
            "barcode",
            "item_code",
            "col5",
            "ชื่อสินค้า_สถานะ",
        ]

        # แปลงข้อมูลตัวเลข
        df_clean["จำนวนคงเหลือ"] = pd.to_numeric(
            df_clean["จำนวนคงเหลือ"], errors="coerce"
        ).fillna(0)

        # ทำความสะอาด Barcode และ Item Code
        def clean_code(val):
            if pd.isna(val):
                return ""
            return str(val).split(".")[0].strip()

        df_clean["barcode"] = df_clean["barcode"].apply(clean_code)
        df_clean["item_code"] = df_clean["item_code"].apply(clean_code)

        # แยกชื่อสินค้า และ สถานะ (พร้อมขาย/เลิกขาย)
        def parse_name_status(val):
            if pd.isna(val):
                return "", ""
            val_str = str(val).strip()
            if ":" in val_str:
                parts = val_str.rsplit(":", 1)
                return parts[0].strip(), parts[1].strip()
            return val_str, ""

        df_clean[["ชื่อสินค้า", "สถานะ"]] = df_clean[
            "ชื่อสินค้า_สถานะ"
        ].apply(lambda x: pd.Series(parse_name_status(x)))
        df_clean["โซน"] = (
            df_clean["โซน"].str.replace("โซน : ", "").str.strip()
        )

        export_cols = [
            "โซน",
            "จำนวนคงเหลือ",
            "barcode",
            "item_code",
            "ชื่อสินค้า",
            "สถานะ",
        ]
        final_df = df_clean[export_cols].reset_index(drop=True)

        # ส่งออกไฟล์ CSV Cleaned เดิม
        final_df.to_csv(
            "TKKERP_Cleaned_All.csv", index=False, encoding="utf-8-sig"
        )
        return final_df
    except Exception as e:
        print(f"Excel read error or fallback: {e}")
        return pd.DataFrame()


# โหลดข้อมูลเข้าสู่ Data Memory
df_master = load_and_clean_excel()

# ----------------------------------------------------
# 2. รายชื่อ 18 โซนหลัก
# ----------------------------------------------------
ALL_18_ZONES = [
    "AA",
    "BB",
    "CC",
    "DD",
    "EE",
    "FF",
    "GG",
    "HH",
    "II",
    "JJ",
    "KK",
    "LL",
    "MM",
    "NN",
    "OO",
    "PP",
    "QQ",
    "IC",
]


# ----------------------------------------------------
# 3. ฟังก์ชันกรองช่วงสต็อกตามเงื่อนไข
# ----------------------------------------------------
def filter_by_stock_range(df: pd.DataFrame, stock_range: str) -> pd.DataFrame:
    if stock_range == "0 ถึง -1000":
        return df[(df["จำนวนคงเหลือ"] <= 0) & (df["จำนวนคงเหลือ"] >= -1000)]
    elif stock_range == "1-10":
        return df[(df["จำนวนคงเหลือ"] >= 1) & (df["จำนวนคงเหลือ"] <= 10)]
    elif stock_range == "10-20":
        return df[(df["จำนวนคงเหลือ"] > 10) & (df["จำนวนคงเหลือ"] <= 20)]
    elif stock_range == "20-30":
        return df[(df["จำนวนคงเหลือ"] > 20) & (df["จำนวนคงเหลือ"] <= 30)]
    elif stock_range == "30-40":
        return df[(df["จำนวนคงเหลือ"] > 30) & (df["จำนวนคงเหลือ"] <= 40)]
    elif stock_range == "40-50":
        return df[(df["จำนวนคงเหลือ"] > 40) & (df["จำนวนคงเหลือ"] <= 50)]
    elif stock_range == "50-100":
        return df[(df["จำนวนคงเหลือ"] > 50) & (df["จำนวนคงเหลือ"] <= 100)]
    elif stock_range == "100-200":
        return df[(df["จำนวนคงเหลือ"] > 100) & (df["จำนวนคงเหลือ"] <= 200)]
    return df


# ----------------------------------------------------
# 4. API Endpoints
# ----------------------------------------------------
@app.get("/api/v1/zones")
def get_zones():
    """ดึงรายชื่อ 18 โซน"""
    return {"zones": ALL_18_ZONES}


@app.get("/api/v1/products/manage")
def manage_products(
    zone: str = Query(..., description="โซนที่ต้องการดู เช่น AA, BB, ..."),
    stock_range: Optional[str] = Query(
        None,
        description="ช่วงสต็อก: '0 ถึง -1000', '1-10', '10-20', '20-30', '30-40', '40-50', '50-100', '100-200'",
    ),
):
    """API สำหรับหน้าจัดการสินค้าแยก 18 โซน และกรองช่วงสต็อก"""
    filtered = df_master[df_master["โซน"] == zone].copy()

    if stock_range:
        filtered = filter_by_stock_range(filtered, stock_range)

    return {
        "zone": zone,
        "stock_range_filter": stock_range or "ทั้งหมด",
        "total_items": len(filtered),
        "items": filtered.to_dict(orient="records"),
    }
