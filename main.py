import os
from dotenv import load_dotenv
import openai
import requests
import json
import time
import logging
from datetime import datetime
import streamlit as st

# Cargar variables de entorno
load_dotenv()

# Configurar el cliente de OpenAI
client = openai.OpenAI()
model = "gpt-3.5-turbo"

# IDs predefinidos (usar después de la primera ejecución)
thread_id = "thread_2H5aUYQn551vRHXMDteXpcxP"
assis_id = "asst_PE5MshFF9ss29SRYBbwF58QG"

# Definir extensiones permitidas
ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.json', '.csv', '.md', '.xlsx', '.docx'}

# Inicializar estados de sesión
if "file_id_list" not in st.session_state:
    st.session_state.file_id_list = []

if "start_chat" not in st.session_state:
    st.session_state.start_chat = False

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

# Configuración de la página
st.set_page_config(page_title="Study Buddy - Charlar y aprender", page_icon=":books:")

def is_valid_file(filename):
    # Lista de extensiones permitidas sin el punto
    ALLOWED_EXTENSIONS = {'pdf', 'txt', 'json', 'csv', 'md', 'xlsx', 'docx'}
    # Obtener la extensión sin el punto
    extension = filename.split('.')[-1].lower() if '.' in filename else ''
    return extension in ALLOWED_EXTENSIONS

def cleanup_temp_files(filename):
    try:
        if os.path.exists(filename):
            os.remove(filename)
    except Exception as e:
        st.warning(f"No se pudo eliminar el archivo temporal: {str(e)}")

def upload_to_openai(filepath):
    try:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"El archivo {filepath} no existe")
            
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            raise ValueError("El archivo está vacío")
            
        with open(filepath, "rb") as file:
            # Intentamos subir el archivo
            response = client.files.create(
                file=file,
                purpose="assistants"
            )
            return response.id
    except Exception as e:
        st.error(f"Error al subir el archivo a OpenAI: {str(e)}")
        return None
    finally:
        # Limpiamos el archivo temporal
        cleanup_temp_files(filepath)

def process_message_with_citations(message):
    """Extract content and annotations from the message and format citations as footnotes."""
    message_content = message.content[0].text
    annotations = (
        message_content.annotations if hasattr(message_content, "annotations") else []
    )
    citations = []

    # Iterate over the annotations and add footnotes
    for index, annotation in enumerate(annotations):
        # Replace the text with a footnote
        message_content.value = message_content.value.replace(
            annotation.text, f" [{index + 1}]"
        )

        # Gather citations based on annotation attributes
        if file_citation := getattr(annotation, "file_citation", None):
            cited_file = {"filename": "documento.pdf"}
            citations.append(
                f'[{index + 1}] {file_citation.quote} from {cited_file["filename"]}'
            )
        elif file_path := getattr(annotation, "file_path", None):
            cited_file = {"filename": "documento.pdf"}
            citations.append(
                f'[{index + 1}] Click [here](#) to download {cited_file["filename"]}'
            )

    # Add footnotes to the end of the message content
    full_response = message_content.value + "\n\n" + "\n".join(citations)
    return full_response

# Interfaz principal
st.title("Study Buddy")
st.write("Aprende rápido chateando con tus documentos")

# Barra lateral para subida de archivos
st.sidebar.markdown("### Subir Documentos")
st.sidebar.markdown("Formatos soportados: PDF, TXT, JSON, CSV, MD, XLSX, DOCX")
file_uploaded = st.sidebar.file_uploader(
    "Subir archivo para convertir en embeddings",
    key="file_upload",
    type=['pdf', 'txt', 'json', 'csv', 'md', 'xlsx', 'docx'],
    accept_multiple_files=False
)

# Botón para subir archivo
if st.sidebar.button("Subir Archivo"):
    if file_uploaded:
        try:
            # Verificamos que el archivo es válido
            if is_valid_file(file_uploaded.name):
                # Guardamos el archivo temporalmente
                temp_file_path = os.path.join(os.getcwd(), file_uploaded.name)
                with open(temp_file_path, "wb") as f:
                    f.write(file_uploaded.getbuffer())
                
                # Subimos el archivo a OpenAI
                file_id = upload_to_openai(temp_file_path)
                
                if file_id:
                    st.session_state.file_id_list.append(file_id)
                    st.sidebar.success(f"Archivo subido exitosamente. ID: {file_id}")
                    
                    try:
                        # Asociamos el archivo con el asistente
                        assistant_file = client.beta.assistants.files.create(
                            assistant_id=assis_id,
                            file_id=file_id
                        )
                        st.sidebar.success("Archivo asociado correctamente con el asistente")
                    except Exception as e:
                        st.sidebar.error(f"Error al asociar el archivo con el asistente: {str(e)}")
                else:
                    st.sidebar.error("No se pudo subir el archivo a OpenAI")
            else:
                st.sidebar.error(f"Tipo de archivo no soportado. El archivo debe ser: pdf, txt, json, csv, md, xlsx o docx")
        except Exception as e:
            st.sidebar.error(f"Error al procesar el archivo: {str(e)}")

# Mostrar IDs de archivos subidos
if st.session_state.file_id_list:
    st.sidebar.write("IDs de archivos subidos:")
    for file_id in st.session_state.file_id_list:
        st.sidebar.write(file_id)

# Botón para iniciar chat
if st.sidebar.button("Iniciar Chat"):
    if st.session_state.file_id_list:
        st.session_state.start_chat = True
        chat_thread = client.beta.threads.create()
        st.session_state.thread_id = chat_thread.id
        st.write("ID del hilo:", chat_thread.id)
    else:
        st.sidebar.warning(
            "No hay archivos subidos. Por favor, sube al menos un archivo para comenzar."
        )

# Interfaz principal del chat
if st.session_state.start_chat:
    if "openai_model" not in st.session_state:
        st.session_state.openai_model = "gpt-3.5-turbo"
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Mostrar mensajes existentes
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Input del chat
    if prompt := st.chat_input("¿Qué quieres preguntar?"):
        # Agregar mensaje del usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Agregar mensaje al hilo
        client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id,
            role="user",
            content=prompt
        )

        # Crear y ejecutar con instrucciones
        run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread_id,
            assistant_id=assis_id,
            instructions="""Por favor, responde a las preguntas utilizando el conocimiento proporcionado en los archivos.
            Cuando agregues información adicional, asegúrate de distinguirla con texto en negrita o subrayado. 
            IMPORTANTE: Todas las respuestas DEBEN ser siempre en español, independientemente del idioma de los documentos.""",
        )

        # Spinner mientras se procesa la respuesta
        with st.spinner("Espera... Generando respuesta..."):
            while run.status != "completed":
                time.sleep(1)
                run = client.beta.threads.runs.retrieve(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id
                )

            # Recuperar mensajes del asistente
            messages = client.beta.threads.messages.list(
                thread_id=st.session_state.thread_id
            )

            # Procesar y mostrar mensajes del asistente
            assistant_messages_for_run = [
                message
                for message in messages
                if message.run_id == run.id and message.role == "assistant"
            ]

            for message in assistant_messages_for_run:
                full_response = process_message_with_citations(message=message)
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response}
                )
                with st.chat_message("assistant"):
                    st.markdown(full_response, unsafe_allow_html=True)

    else:
        st.write(
            "Por favor, sube al menos un archivo y haz clic en 'Iniciar Chat' para comenzar"
        )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)