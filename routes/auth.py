from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from extensions import db, login_manager
from models import Admin
import time

auth_bp = Blueprint('auth', __name__)

# ── Rate limiting sederhana in-memory ───────────────────────
_attempts: dict = {}
MAX_ATTEMPTS  = 5
LOCKOUT_SECS  = 300

def _can_try(ip):
    now  = time.time()
    data = _attempts.get(ip, {})
    if data.get('lockout_until', 0) > now:
        return False, int(data['lockout_until'] - now)
    if data.get('lockout_until', 0) and data['lockout_until'] <= now:
        _attempts.pop(ip, None)
    return True, 0

def _fail(ip):
    data = _attempts.setdefault(ip, {'count': 0, 'lockout_until': 0})
    data['count'] += 1
    if data['count'] >= MAX_ATTEMPTS:
        data['lockout_until'] = time.time() + LOCKOUT_SECS

def _reset(ip):
    _attempts.pop(ip, None)
# ────────────────────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))


@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    ip = request.remote_addr or '0.0.0.0'
    if request.method == 'POST':
        ok, remaining = _can_try(ip)
        if not ok:
            m, s = remaining // 60, remaining % 60
            flash(f'Terlalu banyak percobaan gagal. Coba lagi dalam {m}m {s}d.', 'danger')
            return render_template('login.html')

        identifier = request.form.get('identifier', '').strip()
        password   = request.form.get('password', '').strip()
        admin = Admin.query.filter(
            (Admin.username == identifier) | (Admin.email == identifier)
        ).first()

        if admin and check_password_hash(admin.password, password):
            _reset(ip)
            login_user(admin, remember=True)
            if admin.must_change_password:
                flash('Demi keamanan, wajib ganti password sebelum melanjutkan.', 'warning')
                return redirect(url_for('auth.ganti_password'))
            flash(f'Selamat datang, {admin.nama}!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            _fail(ip)
            sisa = MAX_ATTEMPTS - _attempts.get(ip, {}).get('count', 0)
            if sisa > 0:
                flash(f'Username/email atau password salah! ({sisa} percobaan tersisa)', 'danger')
            else:
                flash('Akun dikunci 5 menit karena terlalu banyak percobaan gagal.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Anda telah keluar.', 'info')
    return redirect(url_for('auth.login'))


# ── Ganti Password ──────────────────────────────────────────
@auth_bp.route('/ganti-password', methods=['GET', 'POST'])
@login_required
def ganti_password():
    if request.method == 'POST':
        pw_lama  = request.form.get('password_lama', '').strip()
        pw_baru  = request.form.get('password_baru', '').strip()
        konfirm  = request.form.get('konfirmasi', '').strip()

        if not current_user.must_change_password:
            if not check_password_hash(current_user.password, pw_lama):
                flash('Password lama tidak sesuai!', 'danger')
                return render_template('ganti_password.html')

        if len(pw_baru) < 8:
            flash('Password baru minimal 8 karakter!', 'danger')
            return render_template('ganti_password.html')
        if pw_baru != konfirm:
            flash('Konfirmasi password tidak cocok!', 'danger')
            return render_template('ganti_password.html')
        if pw_baru == 'admin123':
            flash('Password baru tidak boleh sama dengan password default!', 'danger')
            return render_template('ganti_password.html')

        current_user.password             = generate_password_hash(pw_baru)
        current_user.must_change_password = False
        db.session.commit()
        flash('Password berhasil diubah!', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('ganti_password.html')


# ── Manajemen Admin ─────────────────────────────────────────
@auth_bp.route('/admin')
@login_required
def admin_list():
    admins = Admin.query.order_by(Admin.dibuat).all()
    return render_template('admin_list.html', admins=admins)


@auth_bp.route('/admin/tambah', methods=['POST'])
@login_required
def admin_tambah():
    username = request.form.get('username', '').strip()
    email    = request.form.get('email', '').strip()
    nama     = request.form.get('nama', '').strip()
    password = request.form.get('password', '').strip()

    if not all([username, email, nama, password]):
        flash('Semua field wajib diisi!', 'danger')
        return redirect(url_for('auth.admin_list'))
    if len(password) < 8:
        flash('Password minimal 8 karakter!', 'danger')
        return redirect(url_for('auth.admin_list'))
    if Admin.query.filter((Admin.username == username) | (Admin.email == email)).first():
        flash('Username atau email sudah digunakan!', 'danger')
        return redirect(url_for('auth.admin_list'))

    db.session.add(Admin(
        username=username, email=email, nama=nama,
        password=generate_password_hash(password),
        must_change_password=True
    ))
    db.session.commit()
    flash(f'Admin "{nama}" berhasil ditambahkan. Wajib ganti password saat login pertama.', 'success')
    return redirect(url_for('auth.admin_list'))


@auth_bp.route('/admin/hapus/<int:id>', methods=['POST'])
@login_required
def admin_hapus(id):
    if id == current_user.id:
        flash('Tidak dapat menghapus akun sendiri!', 'danger')
        return redirect(url_for('auth.admin_list'))
    if Admin.query.count() <= 1:
        flash('Harus ada minimal 1 admin!', 'danger')
        return redirect(url_for('auth.admin_list'))
    a = Admin.query.get_or_404(id)
    nama = a.nama
    db.session.delete(a)
    db.session.commit()
    flash(f'Admin "{nama}" berhasil dihapus.', 'success')
    return redirect(url_for('auth.admin_list'))


@auth_bp.route('/admin/reset-password/<int:id>', methods=['POST'])
@login_required
def admin_reset_password(id):
    a = Admin.query.get_or_404(id)
    pw_baru = request.form.get('password_baru', '').strip()
    if len(pw_baru) < 8:
        flash('Password minimal 8 karakter!', 'danger')
        return redirect(url_for('auth.admin_list'))
    a.password             = generate_password_hash(pw_baru)
    a.must_change_password = True
    db.session.commit()
    flash(f'Password {a.nama} direset. Wajib ganti saat login berikutnya.', 'success')
    return redirect(url_for('auth.admin_list'))
