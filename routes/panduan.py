from flask import Blueprint, render_template, Response
from flask_login import login_required
import socket, io, qrcode

panduan_bp = Blueprint('panduan', __name__)

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'

@panduan_bp.route('/panduan')
@login_required
def index():
    return render_template('absensi_panduan.html', server_ip=get_ip())

@panduan_bp.route('/panduan/qr-web')
@login_required
def qr_web():
    """Generate QR Code berisi URL web server."""
    ip  = get_ip()
    url = f'http://{ip}:5000'
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/png')
