from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

from lib.paper_form import convert_form

app = Flask(__name__)
CORS(app)

@app.route('/image', methods=['POST'])
def from_image():
    """
    Convert a paper form image or PDF to a QSR form format.
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided. Please upload a file with key "file"'
            }), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400

        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf'}
        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in allowed_extensions:
            return jsonify({
                'success': False,
                'error': f'Invalid file type. Allowed types: {", ".join(allowed_extensions)}'
            }), 400

        # Save temporarily to disk.
        temp_dir = Path('./temp')
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / f"upload_{file.filename}"
        file.save(str(temp_path))

        try:
            form_output = convert_form(str(temp_path))

            return jsonify({
                'success': True,
                'results': form_output,
                'message': 'Form converted successfully'
            }), 200

        finally:
            if temp_path.exists():
                temp_path.unlink()

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint.
    """
    return jsonify({
        'status': 'healthy',
        'service': 'form-converter'
    }), 200


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=3000)
