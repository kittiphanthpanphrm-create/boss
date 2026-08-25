import numpy as np
import pandas as pd
import streamlit as st

# ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="ระบบจัดการคลังสินค้า", layout="wide")


@st.cache_data
def load_data(file_path="TKKERP (5).xlsx"):
    try:
        df = pd.read_excel(file_path, sheet_name="Sheet1")
    except Exception:
        # กรณีไม่มีไฟล์ต้นทาง ให้สร้าง Mock Data จำลองสำหรับทดสอบระบบ
        zones_list = [
            f"โซน {chr(65+i)}{chr(65+j)}"
            for i in range(3)
            for j in range(6)
        ][:18]
        return pd.DataFrame(
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

    # คลีนข้อมูลจริงจากไฟล์ Excel
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
    df_clean["จำนวนคงเหลือ"] = pd.to_numeric(
        df_clean["จำนวนคงเหลือ"], errors="coerce"
    ).fillna(0)

    def clean_code(val):
        if pd.isna(val):
            return ""
        return str(val).split(".")[0].strip()

    df_clean["barcode"] = df_clean["barcode"].apply(clean_code)
    df_clean["item_code"] = df_clean["item_code"].apply(clean_code)

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
    df_clean["โซน"] = df_clean["โซน"].str.replace("โซน : ", "").str.strip()

    export_cols = [
        "โซน",
        "จำนวนคงเหลือ",
        "barcode",
        "item_code",
        "ชื่อสินค้า",
        "สถานะ",
    ]
    return df_clean[export_cols].reset_index(drop=True)


# โหลดข้อมูล
df_inventory = load_data()

# รายชื่อ 18 โซน (สามารถปรับเปลี่ยนชื่อให้ตรงกับหน้างานจริงได้)
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

# เมนูหลักด้านข้าง (Sidebar)
st.sidebar.title("📦 เมนูระบบ")
menu = st.sidebar.radio(
    "เลือกฟังก์ชันการทำงาน", ["หน้าหลัก", "จัดการสินค้า (18 โซน)"]
)

if menu == "หน้าหลัก":
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
    st.info("👈 กรุณาคลิกเลือกเมนู **'จัดการสินค้า (18 โซน)'** ที่แถบเมนูด้านซ้ายเพื่อเริ่มจัดการ")

elif menu == "จัดการสินค้า (18 โซน)":
    st.title("📑 ระบบจัดการสินค้าแยกรายโซน (18 โซน)")

    # 1. ส่วนเลือกโซน
    selected_zone = st.selectbox(
        "📍 เลือกโซนที่ต้องการตรวจสอบ (18 โซน):",
        options=ALL_18_ZONES,
        index=0,
    )

    # 2. ส่วนเลือกช่วงสต็อก
    stock_ranges = [
        "ทั้งหมด",
        "0 ถึง -1000 (สต็อกติดลบ/หมด)",
        "1 - 10",
        "10 - 20",
        "20 - 30",
        "30 - 40",
        "40 - 50",
        "50 - 100",
        "100 - 200",
        "มากกว่า 200",
    ]

    selected_range = st.radio(
        "🔢 เลือกระดับจำนวนสต็อกคงเหลือ:",
        options=stock_ranges,
        horizontal=True,
    )

    # กรองข้อมูลตามโซน
    filtered_df = df_inventory[df_inventory["โซน"] == selected_zone].copy()

    # กรองข้อมูลตามช่วงสต็อก
    if selected_range == "0 ถึง -1000 (สต็อกติดลบ/หมด)":
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
    elif selected_range == "มากกว่า 200":
        filtered_df = filtered_df[filtered_df["จำนวนคงเหลือ"] > 200]

    st.markdown("---")

    # สรุปผลการค้นหา
    col_stat1, col_stat2, col_stat3 = st.columns(3)
    col_stat1.metric("โซนปัจจุบัน", f"โซน {selected_zone}")
    col_stat2.metric("เงื่อนไขสต็อก", selected_range)
    col_stat3.metric("พบข้อมูล", f"{len(filtered_df):,} รายการ")

    # ตารางแสดงรายการสินค้า
    if not filtered_df.empty:
        # ฟังก์ชันจัดสีแจ้งเตือนสต็อกติดลบ
        def highlight_negative(val):
            color = "#ffcccc" if isinstance(val, (int, float)) and val < 0 else ""
            return f"background-color: {color}"

        styled_df = filtered_df.style.map(
            highlight_negative, subset=["จำนวนคงเหลือ"]
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

        # ปุ่มดาวน์โหลดรายงานเฉพาะรายการที่กรอง
        csv_data = filtered_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 ดาวน์โหลดรายการที่เลือกเป็น CSV",
            data=csv_data,
            file_name=f"stock_zone_{selected_zone}_{selected_range}.csv",
            mime="text/csv",
        )
    else:
        st.warning(
            f"⚠️ ไม่พบสินค้าใน โซน {selected_zone} ที่ตรงกับเงื่อนไขสต็อก '{selected_range}'"
        )
