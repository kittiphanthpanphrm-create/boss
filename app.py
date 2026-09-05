def render_product_cards(items_df, current_zone, is_problem=False):
    cols = st.columns(3)
    for idx, row in items_df.iterrows():
        # ทำความสะอาดรหัสสินค้าและรหัสรอง
        raw_barcode = str(row.get("รหัสสินค้า", "")).replace(".0", "").strip()
        barcode = re.sub(r'[^0-9A-Za-z_-]', '', raw_barcode)
        
        raw_sub = str(row.get("รหัสรอง", "")).replace(".0", "").strip()
        sub_code = re.sub(r'[^0-9A-Za-z_-]', '', raw_sub)
        
        name = str(row.get("ชื่อรายการสินค้า", "")).strip()
        qty = row.get("จำนวนสั่งล่าสุด", 0)
        stock = row.get("คงเหลือ", 0)
        
        # กำหนด URL รูปภาพ (優先ดึงจากบาร์โค้ด หากไม่มีใช้รหัสรอง)
        code_for_img = barcode if (barcode and len(barcode) >= 5) else sub_code
        img_url = f"https://tkkonlineshop.com/images/products/{code_for_img}.jpg"
        web_link = f"https://tkkonlineshop.com/products/{code_for_img}" if code_for_img else "https://tkkonlineshop.com"
        
        with cols[idx % 3]:
            with st.container(border=True):
                # แสดงรูปภาพพร้อม Fallback
                if code_for_img:
                    try:
                        st.image(
                            img_url, 
                            caption=f"รหัส: {code_for_img}", 
                            use_container_width=True
                        )
                    except Exception:
                        st.markdown(
                            f"""
                            <div style="background-color:#F8FAFC; border:1px dashed #CBD5E1; border-radius:8px; height:180px; display:flex; align-items:center; justify-content:center; flex-direction:column; color:#64748B;">
                                <span style="font-size:32px;">🖼️</span>
                                <span style="font-size:12px; margin-top:4px;">ไม่พบไฟล์รูปบนระบบเว็บ</span>
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )
                else:
                    st.markdown(
                        f"""
                        <div style="background-color:#F8FAFC; border:1px dashed #CBD5E1; border-radius:8px; height:180px; display:flex; align-items:center; justify-content:center; flex-direction:column; color:#64748B;">
                            <span style="font-size:32px;">📦</span>
                            <span style="font-size:12px; margin-top:4px;">ไม่มีรหัสบาร์โค้ด</span>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                    
                st.markdown(f"### **{name}**")
                st.caption(f"**รหัสสินค้า:** `{barcode or '-'}` | **โซน:** `{current_zone}`")
                st.markdown("📋 **รหัสรอง (คลิกเพื่อ Copy):**")
                st.code(sub_code if sub_code else "-", language="text")
                
                if is_problem or parse_numeric_stock(stock) < 0:
                    st.markdown(f"🚨 **คงเหลือ:** :red[{stock}] | 🛒 **สั่งล่าสุด:** **{qty}**")
                else:
                    st.markdown(f"📦 **คงเหลือ:** **{stock}** | 🛒 **สั่งล่าสุด:** **{qty}**")
                    
                if code_for_img:
                    st.link_button("🌐 เปิดดูบนเว็บ TKK Online", web_link, use_container_width=True)
