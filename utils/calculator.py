
# utils/calculator.py - Fungsi Kalkulator Kesehatan untuk Mirai

def calculate_bmi(weight_kg: float, height_cm: float) -> dict:
    """
    Menghitung Body Mass Index (BMI) dan memberikan kategori serta saran.
    Tinggi dalam cm akan dikonversi ke meter.
    """
    if not (isinstance(weight_kg, (int, float)) and weight_kg > 0):
        raise ValueError("Berat badan harus angka positif.")
    if not (isinstance(height_cm, (int, float)) and height_cm > 0):
        raise ValueError("Tinggi badan harus angka positif.")

    height_m = height_cm / 100
    bmi = weight_kg / (height_m ** 2)

    category = ""
    advice = ""

    if bmi < 18.5:
        category = "Kekurangan berat badan"
        advice = "Pertimbangkan untuk menambah asupan nutrisi dan berkonsultasi dengan ahli gizi."
    elif 18.5 <= bmi < 24.9:
        category = "Berat badan normal"
        advice = "Pertahankan gaya hidup sehatmu!"
    elif 25 <= bmi < 29.9:
        category = "Kelebihan berat badan"
        advice = "Coba tingkatkan aktivitas fisik dan perhatikan pola makanmu."
    else:
        category = "Obesitas"
        advice = "Sangat disarankan untuk berkonsultasi dengan dokter atau ahli gizi untuk rencana pengelolaan berat badan yang tepat."

    return {"bmi": round(bmi, 2), "category": category, "advice": advice}

def calculate_daily_water_intake(weight_kg: float) -> dict:
    """
    Menghitung perkiraan kebutuhan air harian dalam liter berdasarkan berat badan.
    """
    if not (isinstance(weight_kg, (int, float)) and weight_kg > 0):
        raise ValueError("Berat badan harus angka positif.")

    # Umumnya 30-35 ml per kg berat badan
    water_ml = weight_kg * 33
    water_liter = water_ml / 1000

    advice = "Pastikan kamu minum air yang cukup sepanjang hari untuk menjaga hidrasi tubuhmu. Sesuaikan juga dengan aktivitas fisik dan kondisi cuaca ya!"

    return {"water_liter": round(water_liter, 2), "advice": advice}
