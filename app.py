from flask import Flask, request, render_template, send_file, redirect, jsonify
from pydub import AudioSegment
from pydub.silence import split_on_silence
import speech_recognition as sr
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Ruta para la página principal
@app.route('/')
def index():
    return render_template('upload.html')

# Ruta para subir el archivo y procesarlo
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    
    file = request.files['file']
    
    if file.filename == '':
        return redirect(request.url)
    
    # Aceptar múltiples tipos de archivos de audio
    allowed_extensions = {'wav', 'mp3', 'flac', 'ogg', 'aiff'}
    file_extension = file.filename.rsplit('.', 1)[1].lower()
    
    if file_extension not in allowed_extensions:
        return "Formato de archivo no soportado", 400
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    
    # Archivo para almacenar el progreso
    progress_file = os.path.join(app.config['UPLOAD_FOLDER'], 'progress.txt')

    try:
        # Cargar el archivo de audio completo
        audio = AudioSegment.from_file(file_path, format=file_extension)
        
        # Dividir el audio en partes basadas en el silencio
        chunks = split_on_silence(audio, min_silence_len=1000, silence_thresh=-40)
        
        r = sr.Recognizer()
        full_text = ""
        total_chunks = len(chunks)

        # Procesar cada fragmento y actualizar el progreso
        for i, chunk in enumerate(chunks):
            chunk_filename = os.path.join(app.config['UPLOAD_FOLDER'], f"chunk{i}.{file_extension}")
            chunk.export(chunk_filename, format=file_extension)
            
            try:
                with sr.AudioFile(chunk_filename) as source:
                    audio_chunk = r.listen(source)
                    text = r.recognize_google(audio_chunk, language='es-ES')
                    full_text += text + " "
            except sr.UnknownValueError:
                pass
            except sr.RequestError as e:
                return f"Error en el servicio de Google: {e}"
            except Exception as e:
                return f"Ocurrió un error: {e}"
            
            os.remove(chunk_filename)

            # Actualizar el progreso
            with open(progress_file, 'w') as f:
                f.write(f"{i + 1}/{total_chunks}")

        transcript_path = os.path.join(app.config['UPLOAD_FOLDER'], 'transcripcion.txt')
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        
        # Eliminar el archivo de progreso después de completar
        os.remove(progress_file)
        
        return send_file(transcript_path, as_attachment=True, mimetype='application/octet-stream')
    except Exception as e:
        return f"Ocurrió un error al procesar el archivo: {e}"
    
# Ruta para obtener el progreso del procesamiento
@app.route('/progress')
def progress():
    progress_file = os.path.join(app.config['UPLOAD_FOLDER'], 'progress.txt')
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            progress_info = f.read()
        return jsonify({'progress': progress_info})
    else:
        return jsonify({'progress': '0/0'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Usa el puerto de la variable de entorno o 5000 por defecto
    app.run(host='0.0.0.0', port=port, debug=True)
