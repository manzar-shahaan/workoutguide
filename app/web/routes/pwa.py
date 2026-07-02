# app/web/routes/pwa.py

from flask import send_from_directory

from .. import web_bp


@web_bp.route("/sw.js")
def service_worker():
    # Served from the root path (not /static/sw.js) so its default scope
    # covers the whole site instead of just /static/.
    return send_from_directory(
        f"{web_bp.static_folder}",
        "sw.js",
        mimetype="application/javascript",
    )
