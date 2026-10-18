import os
from PIL import Image, ImageDraw, ImageFont

os.makedirs("data/test_images", exist_ok=True)

def create_receipt_image():
    # Click to'lov kvitansiyasi
    img = Image.new("RGB", (600, 800), color=(245, 247, 250))
    d = ImageDraw.Draw(img)
    
    # Header
    d.rectangle([0, 0, 600, 100], fill=(0, 136, 204))
    d.text((50, 35), "CLICK - To'lov muvaffaqiyatli amalga oshirildi", fill=(255, 255, 255))
    
    # Details
    lines = [
        ("Xizmat nomi:", "MARS ELEKTRON TEXNIKA MCHJ"),
        ("Hisob raqam:", "20208000800208044003"),
        ("Tashkilot INN:", "302568138"),
        ("To'lovchi INN:", "302568138"),
        ("To'lov summasi:", "100 000 UZS"),
        ("Tranzaksiya ID:", "TRX9876543210"),
        ("Sana va vaqt:", "18.10.2026 12:30:15"),
        ("Holati:", "O'TKAZILDI (Muvaffaqiyatli)")
    ]
    y = 140
    for label, val in lines:
        d.text((50, y), label, fill=(100, 100, 100))
        d.text((230, y), val, fill=(20, 20, 20))
        y += 65
    
    path = "data/test_images/click_receipt.png"
    img.save(path)
    print("Saved:", path)
    return path

def create_kassa_chek_image():
    # Kassa savdo cheki (fiskal chek)
    img = Image.new("RGB", (500, 750), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    
    lines = [
        "«QASHQADARYO SAVDO» MCHJ",
        "Savdo do'koni: Shahrisabz filiali",
        "СТИР (INN): 302568138",
        "------------------------------------",
        "SAVDO CHEKI (Onlayn NKM)",
        "Chek raqami: #0004521",
        "1. Qandolat mahsulotlari",
        "   1 x 25 000 = 25 000 UZS",
        "   MXIK (IKPU): 01111001001000000",
        "------------------------------------",
        "JAMI TO'LANDI: 25 000 UZS",
        "NAQD: 25 000 UZS",
        "------------------------------------",
        "Fiskal modul seriya raqami:",
        "FM: LG420210630789",
        "Terminal ID: 99887766",
        "Fiskal belgi: 9812736451",
        "Sana: 18.10.2026 10:15:30",
        "Xaridingiz uchun rahmat!"
    ]
    y = 30
    for line in lines:
        fill = (0, 0, 0)
        d.text((40, y), line, fill=fill)
        y += 35
        
    path = "data/test_images/kassa_chek.png"
    img.save(path)
    print("Saved:", path)
    return path

def create_pos_error_image():
    # POS apparati nosozlik ekrani
    img = Image.new("RGB", (500, 700), color=(30, 30, 35))
    d = ImageDraw.Draw(img)
    
    # Status bar
    d.text((30, 20), "12:35  SIM 1: [||||] 4G  Batareya: 75%", fill=(200, 200, 200))
    d.line([(20, 50), (480, 50)], fill=(80, 80, 80))
    
    # Error box
    d.rectangle([40, 150, 460, 450], outline=(220, 50, 50), width=3)
    d.text((160, 180), "DIQQAT! XATOLIK", fill=(255, 80, 80))
    d.text((80, 240), "Xatolik kodi: 104 (Aloqa uzildi)", fill=(255, 255, 255))
    d.text((60, 290), "Soliq OFD serveri bilan aloqa yo'q.", fill=(200, 200, 200))
    d.text((60, 330), "Internet tarmog'ini tekshiring.", fill=(200, 200, 200))
    d.text((60, 370), "Fiskal modul: LG420210630789", fill=(180, 180, 255))
    
    # Button
    d.rectangle([100, 500, 400, 560], fill=(0, 120, 215))
    d.text((200, 520), "QAYTA URINISH", fill=(255, 255, 255))
    
    path = "data/test_images/pos_error.png"
    img.save(path)
    print("Saved:", path)
    return path

def create_random_image():
    # Begona rasm (tabiat/geometrik rasm, kassa yoki to'lovga aloqasiz)
    img = Image.new("RGB", (500, 500), color=(135, 206, 235))
    d = ImageDraw.Draw(img)
    
    # Sun & grass
    d.ellipse([350, 50, 450, 150], fill=(255, 223, 0))
    d.rectangle([0, 350, 500, 500], fill=(34, 139, 34))
    d.text((150, 400), "Tog' manzarasi - Dam olish", fill=(255, 255, 255))
    
    path = "data/test_images/random_pic.png"
    img.save(path)
    print("Saved:", path)
    return path

if __name__ == "__main__":
    create_receipt_image()
    create_kassa_chek_image()
    create_pos_error_image()
    create_random_image()
