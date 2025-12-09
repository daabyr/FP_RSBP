from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from typing import Optional, List, Dict, Tuple

with open("knowledgeBase.json", "r", encoding="utf-8") as f:
    KB = json.load(f)

BMI_RULES = KB["bmi_rules"]
CONDITION_RULES = KB["condition_rules"]
PREFERENCE_RULES = KB.get("preference_rules", [])
FOODS = KB["foods"]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserInput(BaseModel):
    height_cm: float
    weight_kg: float

    # Kondisi kesehatan
    diabetes: bool = False
    hipertensi: bool = False
    alergi_susu: bool = False
    alergi_seafood: bool = False
    kolesterol: bool = False
    asam_urat: bool = False
    penyakit_jantung: bool = False
    gerd: bool = False

    # Preferensi
    vegetarian: bool = False
    halal: bool = False
    lactose_free: bool = False
    gluten_free: bool = False
    no_seafood: bool = False

def hitung_bmi(weight_kg: float, height_cm: float) -> float:
    height_m = height_cm / 100.0
    return weight_kg / (height_m ** 2)


def hitung_ibw(height_cm: float, target_bmi: float = 24.0) -> float:
    height_m = height_cm / 100.0
    return target_bmi * (height_m ** 2)


def pilih_bmi_rule(bmi: float) -> Optional[dict]:
    for rule in BMI_RULES:
        bmi_min = rule.get("bmi_min")
        bmi_max = rule.get("bmi_max")

        if bmi_min is not None and bmi < bmi_min:
            continue
        if bmi_max is not None and bmi > bmi_max:
            continue
        return rule
    return None


def inference_engine(
    health_facts: Dict[str, bool],
    preference_facts: Dict[str, bool],
) -> Tuple[List[str], List[str]]:

    diet_tags = set()
    tips: List[str] = []

    for rule in CONDITION_RULES:
        fact_name = rule["condition_fact"]
        expected_value = rule["value"]
        if health_facts.get(fact_name) == expected_value:
            for t in rule.get("diet_tags_add", []):
                diet_tags.add(t)
            tips.extend(rule.get("tips", []))

    for rule in PREFERENCE_RULES:
        fact_name = rule["preference_fact"]
        expected_value = rule["value"]
        if preference_facts.get(fact_name) == expected_value:
            for t in rule.get("diet_tags_add", []):
                diet_tags.add(t)
            tips.extend(rule.get("tips", []))

    return list(diet_tags), tips


def pilih_rekomendasi_makanan(
    diet_tags: List[str],
    preference_facts: Dict[str, bool],
) -> List[dict]:

    hasil = []

    vegetarian = preference_facts.get("vegetarian", False)
    halal = preference_facts.get("halal", False)
    lactose_free = preference_facts.get("lactose_free", False)
    gluten_free = preference_facts.get("gluten_free", False)
    no_seafood = preference_facts.get("no_seafood", False)

    for food in FOODS:
        tags = food.get("tags", [])

        if vegetarian and "vegetarian" not in tags:
            continue

        if halal and ("contains_pork" in tags or "contains_alcohol" in tags or "non_halal" in tags):
            continue

        if (lactose_free or "avoid_dairy" in diet_tags) and "dairy" in tags:
            continue

        if (
            no_seafood
            or "avoid_seafood" in diet_tags
            or "avoid_certain_seafood" in diet_tags
        ) and "seafood" in tags:
            continue

        if gluten_free and "contains_gluten" in tags:
            continue

        cocok = True
        for tag in diet_tags:
            if tag == "low_sugar" and "high_sugar" in tags:
                cocok = False
                break
            if tag == "low_glycemic" and "not_low_glycemic" in tags:
                cocok = False
                break
            if tag == "low_sodium" and "high_sodium" in tags:
                cocok = False
                break
            if tag == "low_fat" and "high_fat" in tags:
                cocok = False
                break
            if tag == "low_cholesterol" and "high_cholesterol" in tags:
                cocok = False
                break
            if tag == "limit_potassium" and "high_potassium" in tags:
                cocok = False
                break
            if tag == "low_purine" and "high_purine" in tags:
                cocok = False
                break
            if tag == "avoid_organ_meats" and "organ_meat" in tags:
                cocok = False
                break
            if tag == "avoid_acidic" and "acidic" in tags:
                cocok = False
                break
            if tag == "avoid_caffeine" and "caffeinated" in tags:
                cocok = False
                break
            if tag == "avoid_high_fat" and "high_fat" in tags:
                cocok = False
                break

        if not cocok:
            continue

        hasil.append(food)

    return hasil[:10]


@app.post("/consult")
def consult(user: UserInput):
    bmi = hitung_bmi(user.weight_kg, user.height_cm)
    target_bmi = 24.0
    ibw = hitung_ibw(user.height_cm, target_bmi)

    bmi_rule = pilih_bmi_rule(bmi)
    if bmi_rule:
        protein_per_kg_ibw = bmi_rule["protein_g_per_kg_ibw"]
        cal_min_per_kg = bmi_rule["calories_kcal_per_kg_ibw_min"]
        cal_max_per_kg = bmi_rule["calories_kcal_per_kg_ibw_max"]
    else:
        protein_per_kg_ibw = 1.2
        cal_min_per_kg = 25
        cal_max_per_kg = 30

    protein_grams = protein_per_kg_ibw * ibw
    calories_min = cal_min_per_kg * ibw
    calories_max = cal_max_per_kg * ibw

    health_facts = {
        "diabetes": user.diabetes,
        "hipertensi": user.hipertensi,
        "alergi_susu": user.alergi_susu,
        "alergi_seafoodd": user.alergi_seafood,
        "kolesterol": user.kolesterol,
        "asam_urat": user.asam_urat,
        "penyakit_jantung": user.penyakit_jantung,
        "gerd": user.gerd,
    }

    preference_facts = {
        "vegetarian": user.vegetarian,
        "halal": user.halal,
        "lactose_free": user.lactose_free,
        "gluten_free": user.gluten_free,
        "no_seafood": user.no_seafood,
    }

    diet_tags, tips = inference_engine(health_facts, preference_facts)

    rekomendasi_makanan = pilih_rekomendasi_makanan(
        diet_tags=diet_tags,
        preference_facts=preference_facts,
    )

    target_weight = ibw

    return {
        "bmi": round(bmi, 2),
        "bmi_category": (
            "Underweight" if bmi < 18.5 else
            "Normal" if bmi < 25 else
            "Overweight" if bmi < 30 else
            "Obese"
        ),
        "ibw_kg": round(ibw, 2),
        "target_bmi": target_bmi,
        "target_weight_kg": round(target_weight, 2),
        "protein_grams_per_day": round(protein_grams, 1),
        "calories_min_per_day": round(calories_min),
        "calories_max_per_day": round(calories_max),
        "selected_bmi_rule": bmi_rule["id"] if bmi_rule else None,
        "diet_tags": diet_tags,
        "tips": tips,
        "recommended_foods": [
            {
                "id": food["id"],
                "name": food["name"],
                "per_100g": food["per_100g"],
                "tags": food.get("tags", []),
            }
            for food in rekomendasi_makanan
        ]
    }
