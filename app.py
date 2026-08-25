import os
import re
import numpy as np
import pandas as pd
import streamlit as st

# ตั้งค่าหน้าเว็บ
st.set_page_config(
    page_title="TKK ERP - ระบบจัดการสินค้าและคลัง",
    page_icon="📦",
    layout="wide",
)

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


# ==========================================
# 1. ฟังก์ชันโหลดและประมวลผลข้อมูล
# ==========================================
def clean_dataframe(df_raw):
    # ตรวจสอบโครงสร้างไฟล์
    if "Unnamed: 0" in df_raw.columns:
        df_clean = df_raw.iloc[1:].copy()
        df_clean.columns = [
            "โซน",
            "จำนวนคงเหลือ",
            "ยด",
            "barcode",
            "item_code",
            "col5",
            "ชื่อสินค้า_สถานะ",
        ]
    else:
        df_clean = df_raw.copy()

    # แปลงจำนวนคงเหลือ
    df_clean["จำนวนคงเหลือ"] = pd.to_numeric(
        df_clean["จำนวนคงเหลือ"], errors="coerce"
    ).fillna(0)

    # แปลง Barcode และ Item Code
    def clean_code(val):
        if pd.isna(val):
            return ""
        return str(val).split(".")[0].strip()

    if "barcode" in df_clean.columns:
        df_clean["barcode"] = df_clean["barcode"].apply(clean_code)
    if "item_code" in df_clean.columns:
        df_clean["item_code"] = df_clean["item_code"].apply(clean_code)

    # แยกชื่อสินค้า และ สถานะ
    def parse_name_status(val):
        if pd.isna(val):
            return "", ""
        val_str = str(val).strip()
        if ":" in val_str:
            parts = val_str.rsplit(":", 1)
            return parts[0].strip(), parts[1].strip()
        return val_str, "พร้อมขาย"

    if "ชื่อสินค้า_สถานะ" in df_clean.columns:
        df_clean[["ชื่อสินค้า", "สถานะ"]] = df_clean[
            "ชื่อสินค้า_สถานะ"
        ].apply(lambda x: pd.Series(parse_name_status(x)))
    elif "ชื่อสินค้า" not in df_clean.columns:
        df_clean["ชื่อสินค้า"] = "ไม่ระบุชื่อสินค้า"
        df_clean["สถานะ"] = "พร้อมขาย"

    # จัดการชื่อโซน
    df_clean["โซน"] = (
        df_clean["โซน"]
        .astype(str)
        .str.replace("โซน : ", "")
        .str.replace("โซน", "")
        .str.strip()
    )

    # สกัด Tag เช่น {PV}, {SVP}, {RSS} จากชื่อสินค้า
    def extract_tag(name):
        tags = re.findall(r"\{([^}]+)\}", str(name))
        return tags[0] if tags else "ทั่วไป"

    df_clean["Tag"] = df_clean["ชื่อสินค้า"].apply(extract_tag)

    export_cols = [
        "โซน",
        "จำนวนคงเหลือ",
        "barcode",
        "item_code",
        "ชื่อสินค้า",
        "Tag",
        "สถานะ",
    ]
    cols_to_use = [c for c in export_cols if c in df_clean.columns]
    return df_clean[cols_to_use].reset_index(drop=True)


def get_mock_data():
    zones = ALL_18_ZONES
    tags = ["PV", "SVP", "RSS", "ไพลิน", "หยวน", "CASIO", "ดล", "ทั่วไป"]
    data = []
    for i in range(1, 150):
        data.append(
            {
                "โซน": np.random.choice(zones),
                "จำนวนคงเหลือ": int(np.random.choice([-96, -72, -50, -20, -5, 0, 5, 12, 25, 45, 80, 150])),
                "barcode": f"88500000{i:04d}",
                "item_code": f"{300000 + i}",
                "ชื่อสินค้า": f"•สินค้าตัวอย่างรายการที่ {i}_{{{np.random.choice(tags)}}}TKK",
                "Tag": np.random.choice(tags),
                "สถานะ": np.random.choice(
                    ["พร้อมขาย", "เลิกขาย"], p=[0.7, 0.3]
                ),
            }
        )
    return pd.DataFrame(data)


# ==========================================
# 2. Sidebar & File Upload
# ==========================================
st.sidebar.title("📦 TKK ERP Control")

uploaded_file = st.sidebar.file_uploader(
    "📂 อัปโหลดไฟล์ Excel / CSV", type=["xlsx", "xls", "csv"]
)

# ตรวจสอบการโหลดไฟล์
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".csv"):
            df_raw = pd.read_csv(uploaded_file)
        else:
            df_raw = pd.read_excel(uploaded_file, sheet_name=0)
        df_inventory = clean_dataframe(df_raw)
        st.sidebar.success(f"✔️ โหลดไฟล์ {uploaded_file.name} สำเร็จ")
    except Exception as e:
        st.sidebar.error(f"เกิดข้อผิดพลาดในการอ่านไฟล์: {e}")
        df_inventory = get_mock_data()
elif os.path.exists("TKKERP (5).xlsx"):
    df_raw = pd.read_excel("TKKERP (5).xlsx", sheet_name=0)
    df_inventory = clean_dataframe(df_raw)
elif os.path.exists("TKKERP_Cleaned_All.csv"):
    df_inventory = pd.read_csv("TKKERP_Cleaned_All.csv")
else:
    st.sidebar.info("💡 กำลังใช้ชุดข้อมูลตัวอย่าง (กรุณาอัปโหลดไฟล์ Excel จริง)")
    df_inventory = get_mock_data()

# เมนูหลัก
menu = st.sidebar.radio(
    "🎯 เลือกฟังก์ชันการทำงาน",
    ["📊 ภาพรวมคลังสินค้า", "📑 จัดการสินค้า (18 โซน)", "🔍 ค้นหาสินค้า & Tag"],
)

# ==========================================
# 3. หน้าจอการทำงาน
# ==========================================
if menu == "📊 ภาพรวมคลังสินค้า":
    st.title("📊 ภาพรวมคลังสินค้า TKK ERP")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 รายการสินค้าทั้งหมด", f"{len(df_inventory):,} รายการ")
    c2.metric(
        "✅ สินค้าพร้อมขาย",
        f"{len(df_inventory[df_inventory['สถานะ'] == 'พร้อมขาย']):,} รายการ",
    )
    c3.metric(
        "⛔ สินค้าเลิกขาย",
        f"{len(df_inventory[df_inventory['สถานะ'] == 'เลิกขาย']):,} รายการ",
    )
    c4.metric(
        "⚠️ สต็อกติดลบ",
        f"{len(df_inventory[df_inventory['จำนวนคงเหลือ'] < 0]):,} รายการ",
    )

    st.markdown("---")
    st.subheader("📋 ตารางข้อมูลสินค้าทั้งหมด")

    # ตารางหลัก
    st.dataframe(df_inventory, use_container_width=True, hide_index=True)

    csv_data = df_inventory.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 ดาวน์โหลดข้อมูลทั้งหมด (Cleaned CSV)",
        data=csv_data,
        file_name="TKKERP_Cleaned_All.csv",
        mime="text/csv",
    )

elif menu == "📑 จัดการสินค้า (18 โซน)":
    st.title("📑 ระบบจัดการสินค้าแยกรายโซน (18 โซน)")

    col_z, col_s = st.columns([1, 2])

    with col_z:
        # ฟังก์ชันย่อยที่ 1: เลือกโซนจาก 18 โซน
        selected_zone = st.selectbox(
            "📍 เลือกโซนที่ต้องการตรวจสอบ (18 โซน):",
            options=ALL_18_ZONES,
            index=0,
        )

    with col_s:
        # ฟังก์ชันย่อยที่ 2: เลือกช่วงสต็อก
        stock_ranges = [
            "ทั้งหมด",
            "0 ถึง -1000",
            "1-10",
            "10-20",
            "20-30",
            "30-40",
            "40-50",
            "50-100",
            "100-200",
        ]
        selected_range = st.select_slider(
            "🔢 เลือกช่วงจำนวนสต็อกคงเหลือ:", options=stock_ranges, value="ทั้งหมด"
        )

    # ประมวลผลตัวกรอง
    filtered_df = df_inventory[df_inventory["โซน"] == selected_zone].copy()

    if selected_range == "0 ถึง -1000":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] <= 0)
            & (filtered_df["จำนวนคงเหลือ"] >= -1000)
        ]
    elif selected_range == "1-10":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] >= 1)
            & (filtered_df["จำนวนคงเหลือ"] <= 10)
        ]
    elif selected_range == "10-20":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] > 10)
            & (filtered_df["จำนวนคงเหลือ"] <= 20)
        ]
    elif selected_range == "20-30":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] > 20)
            & (filtered_df["จำนวนคงเหลือ"] <= 30)
        ]
    elif selected_range == "30-40":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] > 30)
            & (filtered_df["จำนวนคงเหลือ"] <= 40)
        ]
    elif selected_range == "40-50":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] > 40)
            & (filtered_df["จำนวนคงเหลือ"] <= 50)
        ]
    elif selected_range == "50-100":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] > 50)
            & (filtered_df["จำนวนคงเหลือ"] <= 100)
        ]
    elif selected_range == "100-200":
        filtered_df = filtered_df[
            (filtered_df["จำนวนคงเหลือ"] > 100)
            & (filtered_df["จำนวนคงเหลือ"] <= 200)
        ]

    st.markdown("---")

    # Metrics สรุป
    m1, m2, m3 = st.columns(3)
    m1.metric("📍 โซนที่เลือก", f"โซน {selected_zone}")
    m2.metric("🎯 เงื่อนไขสต็อก", selected_range)
    m3.metric("📦 พบสินค้า", f"{len(filtered_df):,} รายการ")

    if not filtered_df.empty:

        def highlight_neg(val):
            return (
                "background-color: #ffebee; color: #c62828; font-weight: bold;"
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

        csv_filtered = filtered_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label=f"📥 ดาวน์โหลดรายการโซน {selected_zone} ({selected_range})",
            data=csv_filtered,
            file_name=f"zone_{selected_zone}_{selected_range}.csv",
            mime="text/csv",
        )
    else:
        st.warning(
            f"ℹ️ ไม่พบรายการสินค้าใน โซน {selected_zone} ที่ตรงกับช่วงสต็อก '{selected_range}'"
        )

elif menu == "🔍 ค้นหาสินค้า & Tag":
    st.title("🔍 ค้นหาและจัดกลุ่มสินค้าตาม Tag / รหัส")

    search_kw = st.text_input(
        "🔎 ค้นหาด้วย ชื่อสินค้า / บาร์โค้ด / รหัสสินค้า / Tag:", ""
    )

    if search_kw:
        mask = (
            df_inventory["ชื่อสินค้า"]
            .astype(str)
            .str.contains(search_kw, case=False, na=False)
            | df_inventory["barcode"]
            .astype(str)
            .str.contains(search_kw, case=False, na=False)
            | df_inventory["item_code"]
            .astype(str)
            .str.contains(search_kw, case=False, na=False)
            | df_inventory["Tag"]
            .astype(str)
            .str.contains(search_kw, case=False, na=False)
        )
        res_df = df_inventory[mask]
        st.write(f"ผลการค้นหา: พบ **{len(res_df)}** รายการ")
        st.dataframe(res_df, use_container_width=True, hide_index=True)
    else:
        st.info("💡 พิมพ์คำค้นหา เช่น ชื่อสินค้า, Tag เช่น `PV`, `SVP`, หรือรหัสสินค้า เพื่อค้นหาด่วน")
