import streamlit as st
import pandas as pd
import plotly.express as px
import re
import io
import os
import requests
from pypdf import PdfReader

st.set_page_config(page_title="ระบบแยกคอลัมน์ & แดชบอร์ดสินค้า", layout="wide")

# กำหนดชื่อไฟล์สำหรับจัดเก็บข้อมูลถาวร
DB_FILE = "database_inventory.csv"

# โหลดข้อมูลเดิมจากพื้นที่จัดเก็บ
def load_database():
    if os.path.exists(DB_FILE):
        try:
            return pd.read_csv(DB_FILE, dtype=str)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

# บันทึกข้อมูลลงพื้นที่จัดเก็บถาวร
def save_database(df):
    df.to_csv(DB_FILE, index=False)

# ฟังก์ชันแยกข้อมูลจากข้อความ PDF
def extract_fields_from_text(text):
    pattern = re.compile(
        r'(\d{4,5})\s+รหัส\s*:\s*(\d+)\s*รหัสรอง\s*:\s*(\d+)[•\s\-]*(.*?)(?:\{([^}]+)\})?\s*หน่วยนับ\s*:\s*([^คง]+)คงเหลือ\s*:\s*([\-\d\.]+)\s*(เลิกขาย|ขาย)?\s*(\d+)\s*โซน\s*:\s*([A-Za-z0-9]+)',
        re.DOTALL
    )
    matches = pattern.findall(text)
    data = []
    for m in matches:
        raw_tag = m[4] if m[4] else ""
        data.append({
            "#": m[0],
            "รหัสสินค้า": str(m[1]).strip(),
            "รหัสรอง": str(m[2]).strip(),
            "ชื่อรายการสินค้า": m[3].strip(),
            "แท็ก {Tag}": f"{{{raw_tag}}}" if raw_tag else "-",
            "หน่วยนับ": m[5].strip(),
            "จำนวนสั่งล่าสุด": str(int(m[8])) if m[8].isdigit() else "0",
            "โซน": m[9].strip(),
            "คงเหลือ": str(float(m[6])) if m[6] else "0",
            "สถานะ": m[7] if m[7] else "ปกติ"
        })
    return pd.DataFrame(data)

# ฟังก์ชันจัดระเบียบข้อมูลจาก Excel / CSV
def clean_and_prepare_df(raw_df):
    df = raw_df.copy()
    for col in df.columns:
        if "รหัสสินค้า" in str(col) or str(col) == "รหัส":
            df["รหัสสินค้า"] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        if "รหัสรอง" in str(col):
            df["รหัสรอง"] = df[col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
            
    if "แท็ก {Tag}" not in df.columns:
        name_col = next((c for c in df.columns if "ชื่อ" in str(c) or "รายละ" in str(c)), df.columns[3] if len(df.columns) > 3 else df.columns[0])
        def get_tag(x):
            m = re.search(r'\{([^}]+)\}', str(x))
            return f"{{{m.group(1)}}}" if m else "-"
        def get_name(x):
            return re.sub(r'\{[^}]+\}', '', str(x)).strip()
            
        df["แท็ก {Tag}"] = df[name_col].apply(get_tag)
        df["ชื่อรายการสินค้า"] = df[name_col].apply(get_name)
    
    for c in df.columns:
        if "สั่ง" in str(c):
            df["จำนวนสั่งล่าสุด"] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int).astype(str)
        if "คงเหลือ" in str(c):
            df["คงเหลือ"] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(str)
            
    standard_cols = ["รหัสสินค้า", "รหัสรอง", "ชื่อรายการสินค้า", "แท็ก {Tag}", "หน่วยนับ", "จำนวนสั่งล่าสุด", "โซน", "คงเหลือ", "สถานะ"]
    existing_cols = [c for c in standard_cols if c in df.columns]
    return df[existing_cols]

# ตัวแปรจำในหน่วยความจำ
if "current_df" not in st.session_state:
    st.session_state.current_df = load_database()
if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()

# --- แถบเมนูด้านซ้าย (Sidebar) สำหรับจัดการอัปโหลด ---
with st.sidebar:
    st.header("⚙️ จัดการไฟล์ข้อมูล")
    uploaded_files = st.file_uploader(
        "📂 นำเข้าไฟล์ (PDF, CSV, XLSX)", 
        type=["pdf", "csv", "xlsx"], 
        accept_multiple_files=True
    )
    
    if uploaded_files:
        updated = False
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state.processed_files:
                try:
                    new_df = pd.DataFrame()
                    if uploaded_file.name.endswith(".pdf"):
                        reader = PdfReader(uploaded_file)
                        full_text = "".join([page.extract_text() + "\n" for page in reader.pages])
                        new_df = extract_fields_from_text(full_text)
                    elif uploaded_file.name.endswith(".csv"):
                        new_df = clean_and_prepare_df(pd.read_csv(uploaded_file))
                    elif uploaded_file.name.endswith(".xlsx"):
                        new_df = clean_and_prepare_df(pd.read_excel(uploaded_file))
                    
                    if not new_df.empty:
                        if st.session_state.current_df.empty:
                            st.session_state.current_df = new_df
                        else:
                            st.session_state.current_df = pd.concat([st.session_state.current_df, new_df], ignore_index=True)
                            if "รหัสสินค้า" in st.session_state.current_df.columns:
                                st.session_state.current_df.drop_duplicates(subset=["รหัสสินค้า"], keep="last", inplace=True)
                        
                        st.session_state.processed_files.add(uploaded_file.name)
                        updated = True
                except Exception as e:
                    st.error(f"ไฟล์ {uploaded_file.name} ผิดพลาด: {e}")
        
        if updated:
            save_database(st.session_state.current_df)
            st.success("บันทึกข้อมูลเข้าฐานข้อมูลเรียบร้อย!")

    st.divider()
    if st.button("🗑️ ล้างข้อมูลทั้งหมดในระบบ"):
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
        st.session_state.current_df = pd.DataFrame()
        st.session_state.processed_files = set()
        st.rerun()

# --- หน้าแดชบอร์ดหลัก ---
st.title("📦 ระบบจัดการและแดชบอร์ดข้อมูลสินค้า")

df = st.session_state.current_df

if not df.empty:
    # แปลงชนิดข้อมูลสำหรับแสดงผลและคำนวณสถิติ
    qty_sum = pd.to_numeric(df.get("จำนวนสั่งล่าสุด", 0), errors="coerce").fillna(0).sum()
    stock_sum = pd.to_numeric(df.get("คงเหลือ", 0), errors="coerce").fillna(0).sum()
    
    st.success(f"📊 ข้อมูลสินค้าทั้งหมดที่บันทึกไว้ในระบบ: **{len(df):,} รายการ**")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("จำนวนรายการสะสม", f"{len(df):,} รายการ")
    c2.metric("จำนวนแท็กกลุ่มสินค้า", f"{df['แท็ก {Tag}'].nunique():,} กลุ่ม" if 'แท็ก {Tag}' in df.columns else "-")
    c3.metric("รวมยอดสั่งล่าสุด", f"{int(qty_sum):,} ชิ้น")
    c4.metric("รวมสินค้าคงเหลือ", f"{int(stock_sum):,} ชิ้น")

    st.divider()

    # แสดงการ์ดรูปภาพตามแท็ก
    st.subheader("🖼️ แสดงสินค้าและรูปภาพตามกลุ่มแท็ก")
    if "แท็ก {Tag}" in df.columns:
        tag_list = sorted(list(df["แท็ก {Tag}"].dropna().unique()))
        selected_tag = st.selectbox("🏷️ เลือกกลุ่มแท็กสินค้าที่ต้องการดู:", options=tag_list)
        
        if selected_tag:
            filtered_df = df[df["แท็ก {Tag}"] == selected_tag].reset_index(drop=True)
            st.write(f"พบ **{len(filtered_df)} รายการ** ในแท็ก `{selected_tag}`")
            
            cols = st.columns(3)
            for idx, row in filtered_df.iterrows():
                barcode = str(row.get("รหัสสินค้า", "")).strip()
                sub_code = str(row.get("รหัสรอง", "")).strip()
                name = str(row.get("ชื่อรายการสินค้า", "")).strip()
                qty = row.get("จำนวนสั่งล่าสุด", 0)
                stock = row.get("คงเหลือ", 0)
                
                img_url = f"https://tkkonlineshop.com/images/products/{barcode}.jpg"
                
                with cols[idx % 3]:
                    with st.container(border=True):
                        st.image(
                            img_url, 
                            caption=f"รหัส: {barcode}", 
                            use_container_width=True
                        )
                        st.markdown(f"**{name}**")
                        st.caption(f"รหัสสินค้า: `{barcode}`")
                        st.markdown(f"📋 **รหัสรอง (คลิกเพื่อ Copy):**")
                        st.code(sub_code, language="text")
                        st.markdown(f"📦 **คงเหลือ:** {stock} | 🛒 **สั่งล่าสุด:** {qty}")

    st.divider()

    # ตารางรวมและปุ่มดาวน์โหลด
    st.subheader("📋 ตารางรายการข้อมูลสะสมทั้งหมด")
    st.dataframe(df, use_container_width=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="ข้อมูลสินค้าแยกแท็ก", index=False)
    
    st.download_button(
        label="📥 ดาวน์โหลดไฟล์ข้อมูลรวมทั้งหมดเป็น Excel (.xlsx)",
        data=output.getvalue(),
        file_name="สรุปข้อมูลสินค้าสะสมแยกแท็ก.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("👈 กรุณาอัปโหลดไฟล์ข้อมูล (PDF, Excel, CSV) ที่แถบเมนูด้านซ้ายมือเพื่อเริ่มต้น")
