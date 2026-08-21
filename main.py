from fastapi import FastAPI, Request, Depends, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from nanobio_logic import simulate_nano_bioremediation
from database import get_db, SimulationRecord
import uvicorn
import csv
import io

app = FastAPI(
    title="Nano-Bioremediation Simulator with Compliance & Data Storage"
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


class SimulationRequest(BaseModel):
    project_name: str = "Wastewater Project 1"
    contaminant_type: str
    initial_concentration: float
    nano_material: str
    nano_dosage: float
    uv_intensity: float
    biomass_density: float
    contact_time: float
    ph: float


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/api/simulate")
async def run_and_save_simulation(data: SimulationRequest, db: Session = Depends(get_db)):
    # 1. Compute Simulation Results (includes EPA safety limits & optimization metrics)
    sim_output = simulate_nano_bioremediation(data.model_dump())
    results = sim_output.get("simulation_results", {})
    compliance = sim_output.get("compliance_and_optimization", {})

    # 2. Save Input + Output into Database
    record = SimulationRecord(
        project_name=data.project_name,
        contaminant_type=data.contaminant_type,
        initial_concentration=data.initial_concentration,
        nano_material=data.nano_material,
        nano_dosage=data.nano_dosage,
        uv_intensity=data.uv_intensity,
        biomass_density=data.biomass_density,
        contact_time=data.contact_time,
        ph=data.ph,
        effluent_concentration=results.get("effluent_concentration_mg_L", 0.0),
        total_removal_efficiency=results.get(
            "total_removal_efficiency_pct", 0.0),
        nano_phase_efficiency=results.get("nano_phase_efficiency_pct", 0.0),
        bio_phase_efficiency=results.get("bio_phase_efficiency_pct", 0.0),
        bio_viability=results.get("bio_viability_pct", 0.0),
        nano_leaching=results.get("nano_leaching_mg_L", 0.0),
        epa_mcl=compliance.get("epa_mcl_mg_L", 0.0),
        is_compliant=compliance.get("is_compliant", False),
        min_required_dosage=compliance.get("min_required_dosage_mg_L", 0.0),
        required_contact_time=compliance.get("required_contact_time_min", 0.0)
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    sim_output["record_id"] = record.id
    return sim_output


@app.get("/api/history")
async def get_history(db: Session = Depends(get_db)):
    records = db.query(SimulationRecord).order_by(
        SimulationRecord.timestamp.desc()
    ).all()
    return records


@app.get("/api/export/csv")
async def export_csv(db: Session = Depends(get_db)):
    records = db.query(SimulationRecord).all()
    output = io.StringIO()
    writer = csv.writer(output)

    # Header including EPA compliance & optimization fields
    writer.writerow([
        "ID", "Timestamp", "Project Name", "Contaminant", "Initial Conc (mg/L)",
        "Nano Material", "Nano Dosage (mg/L)", "UV Intensity (mW/cm2)",
        "Biomass Density (mg/L)", "Contact Time (min)", "pH",
        "Effluent Conc (mg/L)", "Total Removal (%)", "Bio-Viability (%)",
        "Nano Leaching (mg/L)", "EPA MCL (mg/L)", "Compliant Status",
        "Min Req Dosage (mg/L)", "Req Contact Time (min)"
    ])

    for r in records:
        writer.writerow([
            r.id, r.timestamp, r.project_name, r.contaminant_type, r.initial_concentration,
            r.nano_material, r.nano_dosage, r.uv_intensity, r.biomass_density,
            r.contact_time, r.ph, r.effluent_concentration, r.total_removal_efficiency,
            r.bio_viability, r.nano_leaching,
            getattr(r, 'epa_mcl', 'N/A'),
            "PASS" if getattr(r, 'is_compliant', False) else "FAIL",
            getattr(r, 'min_required_dosage', 'N/A'),
            getattr(r, 'required_contact_time', 'N/A')
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=nano_bioremediation_data.csv"
        }
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
