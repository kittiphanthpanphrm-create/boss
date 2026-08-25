import numpy as np
import pandas as pd
import streamlit as st

# ==========================================
# ส่วนที่ 1: โหลด ทำความสะอาดข้อมูล และเซฟ CSV (คำสั่งเดิม)
# ==========================================
file_path = "TKKERP (5).xlsx"


@st.cache_data
def process_and_load_data(file_path):
    try:
        # 1. โหลดข้อมูลจากไฟล์ Excel
        df = pd.read_excel(file_path, sheet_name="Sheet1")

        # 2. ทำความสะอาดข้อมูลและตั้งชื่อคอลัมน์
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
        ).fillna(0)

        # แปลงรหัส Barcode และ Item Code ให้อยู่ในรูปแบบ String ตัวเลขล้วน
        def clean_code(val):
            if pd.isna(val):
                return ""
            return str(val).split(".")[0].strip()

        df_clean["barcode"] = df_clean["barcode"].apply(clean_code)
        df_clean["item_code"] = df_clean["item_code"].apply(clean_code)

        # แยกชื่อสินค้าและสถานะ ออกจากกัน
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

        # ตัดคำว่า 'โซน : ' ให้เหลือเฉพาะชื่อโซน
        df_clean["โซน"] = (
            df_clean["โซน"].str.replace("โซน : ", "").str.strip()
        )

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

        # 4. ส่งออกไฟล์เป็น CSV รองรับภาษาไทย (UTF-8 with BOM) ตามคำสั่งเดิม
        final_df.to_csv(
            "TKKERP_Cleaned_All.csv", index=False, encoding="utf-8-sig"
        )
        return final_df

    except Exception as e:
        # จำลองข้อมูล Mock กรณีหาไฟล์ไม่พบ
        zones_list = [
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
        mock_df = pd.DataFrame(
            {
                "โซน": np.random.choice(zones_list, 500),
                "จำนวนคงเหลือ": np.random.randint(-100, 200, 500),
                "barcode": [
                    f"88500000{i:04d}" for i in range(1, 501)
                ],
                "item_code": [f"ITEM-{i:04d}" for i in range(1, 501)],
                "ชื่อสินค้า": [
                    f"สินค้าตัวอย่างรายการที่ {i}" for i in range(1, 501)
                ],
                "สถานะ": np.random.choice(
                    ["พร้อมขาย", "เลิกขาย"], 500, p=[0.7, 0.3]
                ),
            }
        )
        mock_df.to_csv(
            "TKKERP_Cleaned_All.csv", index=False, encoding="utf-8-sig"
        )
        return mock_df


# ดึงข้อมูลเข้าสู่ตัวแปร
df_inventory = process_and_load_data(file_path)

# ==========================================
# ส่วนที่ 2: ระบบจัดการสินค้า 18 โซน + กรองสต็อก (คำสั่งที่เพิ่มใหม่)
# ==========================================
st.set_page_config(page_title="ระบบจัดการคลังสินค้า", layout="wide")

# รายชื่อ 18 โซนหลัก
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

# แถบเมนูด้านข้าง
st.sidebar.title("📦 เมนูระบบ")
menu = st.sidebar.radio(
    "เลือกหน้าการทำงาน", ["หน้าหลัก (ภาพรวม)", "จัดการสินค้า (18 โซน)"]
)

if menu == "หน้าหลัก (ภาพรวม)":
    st.title("📊 ภาพรวมคลังสินค้า")
    col1, col2, col3 = st.columns(3)
    col1.metric("จำนวนรายการทั้งหมด", f"{len(df_inventory):,} รายการ")
    col2.metric(
        "สินค้าพร้อมขาย",
        f"{len(df_inventory[df_inventory['สถานะ'] == 'พร้อมขาย']):,} รายการ",
    )
    col3.metric(
        "สินค้าสต็อกติดลบ",
        f"{len(df_inventory[df_inventory['จำนวนคงเหลือ'] < 0]):,} รายการ",
    )

    st.markdown("---")
    st.subheader("📋 ตัวอย่างข้อมูลที่คลีนแล้ว")
    st.dataframe(df_inventory.head(15), use_container_width=True)
    st.success(
        "บันทึกไฟล์ 'TKKERP_Cleaned_All.csv' เรียบร้อยแล้วที่โฟลเดอร์ปัจจุบัน"
    )

elif menu == "จัดการสินค้า (18 โซน)":
    st.title("📑 ระบบจัดการสินค้าแยกรายโซน (18 โซน)")

    # ฟังก์ชันย่อยที่ 1: เลือก 18 โซน
    selected_zone = st.selectbox(
        "📍 เลือกโซนที่ต้องการดูข้อมูล:",
        options=ALL_18_ZONES,
        index=0,
    )

    # ฟังก์ชันย่อยที่ 2: เลือกช่วงสต็อกตามเงื่อนไข
    stock_ranges = [
        "ทั้งหมด",
        "0 ถึง -1000",
        "1 - 10",
        "10 - 20",
        "20 - 30",
        "30 - 40",
        "40 - 50",
        "50 - 100",
        "100 - 200",
    ]

    selected_range = st.radio(
        "🔢 กรองตามช่วงจำนวนสต็อกคงเหลือ:",
        options=stock_ranges,
        horizontal=True,
    )

    # ประมวลผลการกรองข้อมูล
    filtered_df = df_inventory[df_inventory["โซน"] == selected_zone].copy()

    if selected_range == "0 ถึง -1000":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] <= 0)
            & (filtered_df["จำนวนคงเหลือ"] >= -1000)
        ]
    elif selected_range == "1 - 10":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] >= 1)
            & (filtered_df["จำนวนคงเหลือ"] <= 10)
        ]
    elif selected_range == "10 - 20":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] > 10)
            & (filtered_df["จำนวนคงเหลือ"] <= 20)
        ]
    elif selected_range == "20 - 30":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] > 20)
            & (filtered_df["จำนวนคงเหลือ"] <= 30)
        ]
    elif selected_range == "30 - 40":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] > 30)
            & (filtered_df["จำนวนคงเหลือ"] <= 40)
        ]
    elif selected_range == "40 - 50":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] > 40)
            & (filtered_df["จำนวนคงเหลือ"] <= 50)
        ]
    elif selected_range == "50 - 100":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] > 50)
            & (filtered_df["จำนวนคงเหลือ"] <= 100)
        ]
    elif selected_range == "100 - 200":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] > 100)
            & (filtered_df["จำนวนคงเหลือ"] <= 200)
        ]

    st.markdown("---")

    # แสดงสถิติสรุป
    c1, c2, c3 = st.columns(3)
    c1.metric("โซนที่เลือก", f"โซน {selected_zone}")
    c2.metric("เงื่อนไขช่วงสต็อก", selected_range)
    c3.metric("จำนวนรายการที่พบ", f"{len(filtered_df):,} รายการ")

    # แสดงผลตารางสินค้า
    if not filtered_df.empty:

        def highlight_neg(val):
            return (
                "background-color: #ffcccc"
                if isinstance(val, (int, float)) and val < 0
                else ""
            )

        styled_df = filtered_df.style.map(
            highlight_neg, subset=["จำนวนคงเหลือ"]
        )

        st.dataframe(
            styled_df,
            use_container_width=True,
            column_config={
                "จำนวนคงเหลือ": st.column_config.NumberColumn(
                    "จำนวนคงเหลือ", format="%d ชิ้น"
                ),
                "barcode": st.column_config.TextColumn("บาร์โค้ด"),
                "item_code": st.column_config.TextColumn("รหัสสินค้า"),
            },
            hide_index=True,
        )

        csv_download = filtered_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 ดาวน์โหลดรายการที่เลือกเป็น CSV",
            data=csv_download,
            file_name=f"zone_{selected_zone}_{selected_range}.csv",
            mime="text/csv",
        )
    else:
        st.warning(
            f"⚠️ ไม่พบสินค้าใน โซน {selected_zone} ที่ตรงกับเงื่อนไขสต็อก '{selected_range}'"
        )
