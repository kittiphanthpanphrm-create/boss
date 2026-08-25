import pandas as pd

# 1. โหลดข้อมูลจากไฟล์ Excel
file_path = "TKKERP (5).xlsx"
df = pd.read_excel(file_path, sheet_name="Sheet1")

# 2. ทำความสะอาดข้อมูลและตั้งชื่อคอลัมน์
# ข้ามแถวหัวตารางเดิมที่ไม่สมบูรณ์ (แถวแรก)
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

# แปลงประเภทข้อมูลตัวเลข
df_clean["จำนวนคงเหลือ"] = pd.to_numeric(
    df_clean["จำนวนคงเหลือ"], errors="coerce"
)


# แปลงรหัส Barcode และ Item Code ให้อยู่ในรูปแบบ String ตัวเลขล้วน (ตัด .0 ออก)
def clean_code(val):
    if pd.isna(val):
        return ""
    val_str = str(val).split(".")[0].strip()
    return val_str


df_clean["barcode"] = df_clean["barcode"].apply(clean_code)
df_clean["item_code"] = df_clean["item_code"].apply(clean_code)


# แยกชื่อสินค้าและสถานะ (พร้อมขาย / เลิกขาย) ออกจากกัน
def parse_name_status(val):
    if pd.isna(val):
        return "", ""
    val_str = str(val).strip()
    if ":" in val_str:
        parts = val_str.rsplit(":", 1)
        return parts[0].strip(), parts[1].strip()
    return val_str, ""


df_clean[["ชื่อสินค้า", "สถานะ"]] = df_clean["ชื่อสินค้า_สถานะ"].apply(
    lambda x: pd.Series(parse_name_status(x))
)

# ตัดคำว่า 'โซน : ' ให้เหลือเฉพาะชื่อโซน
df_clean["โซน"] = df_clean["โซน"].str.replace("โซน : ", "").str.strip()

# 3. เลือกเฉพาะคอลัมน์ที่ต้องการใช้งาน
export_cols = [
    "โซน",
    "จำนวนคงเหลือ",
    "barcode",
    "item_code",
    "ชื่อสินค้า",
    "สถานะ",
]
final_df = df_clean[export_cols].reset_index(drop=True)

# 4. ส่งออกไฟล์เป็น CSV รองรับภาษาไทย (UTF-8 with BOM)
final_df.to_csv("TKKERP_Cleaned_All.csv", index=False, encoding="utf-8-sig")

print(f"ประมวลผลสำเร็จ: ทั้งหมด {len(final_df)} รายการ")
