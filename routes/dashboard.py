from flask import Blueprint, render_template
from flask_login import login_required
from models import Santri, Acara, Absensi
from extensions import db
from sqlalchemy import func
from datetime import date

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    total_santri  = Santri.query.count()
    total_acara   = Acara.query.count()
    acara_buka    = Acara.query.filter_by(status='buka').count()
    total_absensi = Absensi.query.count()
    tepat_waktu   = Absensi.query.filter_by(status='tepat_waktu').count()
    terlambat     = Absensi.query.filter_by(status='terlambat').count()
    pct_tepat     = round(tepat_waktu / total_absensi * 100) if total_absensi else 0

    recent          = Absensi.query.order_by(Absensi.waktu.desc()).limit(10).all()
    acara_aktif     = Acara.query.filter_by(status='buka').all()
    santri_terakhir = Santri.query.order_by(Santri.dibuat.desc()).limit(5).all()

    # Fix N+1: satu query aggregate untuk chart kehadiran per acara
    hadir_map = dict(
        db.session.query(Absensi.acara_id, func.count(Absensi.id))
        .group_by(Absensi.acara_id).all()
    )
    acara_list   = Acara.query.order_by(Acara.dibuat.desc()).all()
    chart_labels = [a.nama[:15] for a in acara_list]
    chart_data   = [hadir_map.get(a.id, 0) for a in acara_list]

    return render_template('dashboard.html',
        total_santri=total_santri, total_acara=total_acara,
        acara_buka=acara_buka, total_absensi=total_absensi,
        tepat_waktu=tepat_waktu, terlambat=terlambat, pct_tepat=pct_tepat,
        recent=recent, chart_labels=chart_labels, chart_data=chart_data,
        acara_aktif=acara_aktif, santri_terakhir=santri_terakhir,
        today=date.today()
    )
