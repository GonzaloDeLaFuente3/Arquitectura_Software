import os
from dotenv import load_dotenv
import openai
import streamlit as st
import time
import logging
from typing import List, Optional
from datetime import datetime

class StudyBuddyApp:
    ALLOWED_EXTENSIONS = {'pdf', 'txt', 'json', 'csv', 'md', 'xlsx', 'docx'}
    
    def __init__(self):
        self.setup_streamlit()
        self.initialize_session_state()
        self.setup_sidebar()
        
    def setup_streamlit(self):
        """Configuración inicial de la página de Streamlit"""
        st.set_page_config(
            page_title="Study Buddy - Charlar y aprender",
            page_icon=":books:",
            layout="wide"
        )
        
    def initialize_session_state(self):
        """Inicialización de variables de estado de la sesión"""
        session_vars = {
            "file_id_list": [],
            "start_chat": False,
            "thread_id": None,
            "api_key": None,
            "openai_model": "gpt-3.5-turbo",
            "messages": [],
            "assistant_id": None,
            "uploaded_files": []  # Para mantener registro de archivos subidos
        }
        
        for var, default in session_vars.items():
            if var not in st.session_state:
                st.session_state[var] = default
                
    def setup_sidebar(self):
        """Configuración de la barra lateral"""
        st.sidebar.markdown("### Configuración de OpenAI")
        self.handle_api_key_input()
        
    def handle_api_key_input(self):
        """Manejo de la entrada de la API key"""
        api_key_input = st.sidebar.text_input(
            "Ingresa tu API key de OpenAI",
            type="password",
            help="Puedes encontrar tu API key en https://platform.openai.com/account/api-keys"
        )
        
        if st.sidebar.button("Guardar API Key"):
            if api_key_input:
                try:
                    # Verificar la API key intentando hacer una llamada simple
                    client = openai.OpenAI(api_key=api_key_input)
                    client.models.list()  # Verifica si la API key es válida
                    
                    st.session_state.api_key = api_key_input
                    st.sidebar.success("API Key guardada exitosamente!")
                    
                    # Intentar recuperar o crear el asistente
                    self.get_or_create_assistant(client)
                except Exception as e:
                    st.sidebar.error(f"API Key inválida: {str(e)}")
            else:
                st.sidebar.error("Por favor, ingresa una API Key válida")
    
    def get_or_create_assistant(self, client: openai.OpenAI) -> str:
        """Recuperar el asistente existente o crear uno nuevo si no existe"""
        try:
            # Primero, intentar listar los asistentes existentes
            assistants = client.beta.assistants.list(
                order="desc",
                limit=100
            )
            
            # Buscar un asistente existente con el nombre "Study Buddy"
            existing_assistant = next(
                (ass for ass in assistants.data if ass.name == "Study Buddy"),
                None
            )
            
            if existing_assistant:
                st.session_state.assistant_id = existing_assistant.id
                st.sidebar.success("Asistente existente recuperado exitosamente!")
                return existing_assistant.id
            
            # Si no existe, crear uno nuevo
            new_assistant = client.beta.assistants.create(
                name="Study Buddy",
                instructions="""Eres un asistente de estudio amigable y paciente. 
                Tu objetivo es ayudar a comprender el contenido de los documentos proporcionados.
                Responde siempre en español, de manera clara y concisa.
                Cuando agregues información adicional que no está en los documentos, 
                marca esa información con negrita o cursiva para distinguirla.
                Siempre que sea posible, cita las partes relevantes de los documentos en tus respuestas.""",
                model="gpt-3.5-turbo-16k",
                tools=[{"type": "retrieval"}]
            )
            
            st.session_state.assistant_id = new_assistant.id
            st.sidebar.success("Nuevo asistente creado exitosamente!")
            return new_assistant.id
            
        except Exception as e:
            st.error(f"Error al gestionar el asistente: {str(e)}")
            return None
    
    def handle_file_upload(self, client: openai.OpenAI):
        """Manejo de la carga de múltiples archivos"""
        st.sidebar.markdown("### Subir Documentos")
        st.sidebar.markdown(f"Formatos soportados: {', '.join(self.ALLOWED_EXTENSIONS)}")
        
        uploaded_files = st.sidebar.file_uploader(
            "Subir archivos",
            type=list(self.ALLOWED_EXTENSIONS),
            accept_multiple_files=True  # Permitir múltiples archivos
        )
        
        if st.sidebar.button("Procesar Archivos"):
            if uploaded_files:
                for file in uploaded_files:
                    if file.name not in [f.name for f in st.session_state.uploaded_files]:
                        self.process_uploaded_file(client, file)
                        st.session_state.uploaded_files.append(file)
            else:
                st.sidebar.warning("Por favor selecciona al menos un archivo para subir")
        
        # Mostrar archivos cargados
        if st.session_state.file_id_list:
            st.sidebar.markdown("### Archivos Cargados")
            for idx, file in enumerate(st.session_state.uploaded_files):
                st.sidebar.text(f"{idx + 1}. {file.name}")
    
    def process_uploaded_file(self, client: openai.OpenAI, file_uploaded):
        """Procesar el archivo subido"""
        try:
            # Crear archivo temporal
            temp_file_path = os.path.join(os.getcwd(), file_uploaded.name)
            with open(temp_file_path, "wb") as f:
                f.write(file_uploaded.getbuffer())
            
            # Subir archivo a OpenAI
            with open(temp_file_path, "rb") as file:
                response = client.files.create(
                    file=file,
                    purpose="assistants"
                )
                
                file_id = response.id
                st.session_state.file_id_list.append(file_id)
                
                # Asegurarse de que existe un assistant_id
                if not st.session_state.assistant_id:
                    self.get_or_create_assistant(client)
                
                # Asociar archivo con el asistente
                client.beta.assistants.files.create(
                    assistant_id=st.session_state.assistant_id,
                    file_id=file_id
                )
                
                st.sidebar.success(f"Archivo {file_uploaded.name} procesado exitosamente!")
                
        except Exception as e:
            st.sidebar.error(f"Error al procesar el archivo {file_uploaded.name}: {str(e)}")
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    
    def handle_chat(self, client: openai.OpenAI):
        """Manejo de la interfaz y lógica del chat"""
        if not st.session_state.thread_id:
            if st.sidebar.button("Iniciar Chat"):
                if st.session_state.file_id_list:
                    thread = client.beta.threads.create()
                    st.session_state.thread_id = thread.id
                    st.session_state.start_chat = True
                    st.sidebar.success("¡Chat iniciado! Puedes comenzar a hacer preguntas.")
                else:
                    st.sidebar.warning("Sube al menos un archivo para comenzar")
        
        if st.session_state.start_chat:
            self.display_chat_interface(client)
    
    def display_chat_interface(self, client: openai.OpenAI):
        """Mostrar la interfaz del chat y procesar mensajes"""
        # Mostrar archivos disponibles para consulta
        st.markdown("### Archivos disponibles para consulta:")
        for file in st.session_state.uploaded_files:
            st.markdown(f"- {file.name}")
        
        st.markdown("---")
        
        # Mostrar mensajes existentes
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Input del usuario
        if prompt := st.chat_input("¿Qué quieres preguntar sobre los documentos?"):
            self.process_user_message(client, prompt)
    
    def process_user_message(self, client: openai.OpenAI, prompt: str):
        """Procesar mensaje del usuario y obtener respuesta"""
        # Agregar mensaje del usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        try:
            # Crear mensaje en el hilo
            client.beta.threads.messages.create(
                thread_id=st.session_state.thread_id,
                role="user",
                content=prompt
            )
            
            # Ejecutar el asistente
            run = client.beta.threads.runs.create(
                thread_id=st.session_state.thread_id,
                assistant_id=st.session_state.assistant_id,
                instructions="""Responde en español utilizando el contenido de los documentos.
                Cita las partes relevantes de los documentos.
                Si agregas información adicional, márcala en negrita."""
            )
            
            # Esperar respuesta
            with st.spinner("Analizando documentos y procesando tu pregunta..."):
                self.wait_for_run_completion(client, run)
                
        except Exception as e:
            st.error(f"Error al procesar el mensaje: {str(e)}")
    
    def wait_for_run_completion(self, client: openai.OpenAI, run):
        """Esperar a que se complete la ejecución y mostrar la respuesta"""
        while run.status not in ["completed", "failed", "expired"]:
            time.sleep(1)
            run = client.beta.threads.runs.retrieve(
                thread_id=st.session_state.thread_id,
                run_id=run.id
            )
        
        if run.status == "completed":
            messages = client.beta.threads.messages.list(
                thread_id=st.session_state.thread_id
            )
            
            # Procesar solo los nuevos mensajes
            new_messages = [
                msg for msg in messages
                if msg.run_id == run.id and msg.role == "assistant"
            ]
            
            for message in new_messages:
                response = self.process_message_with_citations(message)
                st.session_state.messages.append(
                    {"role": "assistant", "content": response}
                )
                with st.chat_message("assistant"):
                    st.markdown(response, unsafe_allow_html=True)
        else:
            st.error(f"Error en el procesamiento: {run.status}")
    
    @staticmethod
    def process_message_with_citations(message):
        """Procesar mensaje y formatear citas"""
        message_content = message.content[0].text
        annotations = message_content.annotations if hasattr(message_content, "annotations") else []
        citations = []
        
        # Procesar anotaciones y citas
        content = message_content.value
        for idx, annotation in enumerate(annotations):
            if hasattr(annotation, 'file_citation'):
                content = content.replace(
                    annotation.text,
                    f'[{idx + 1}]'
                )
                citations.append(
                    f'[{idx + 1}] {annotation.file_citation.quote}'
                )
        
        return content + ('\n\n' + '\n'.join(citations) if citations else '')
    
    def run(self):
        """Ejecutar la aplicación"""
        st.title("Study Buddy - Compañero de estudio")
        st.write("Aprende rápido chateando con tus documentos")
        
        if not st.session_state.api_key:
            st.warning("Por favor, ingresa tu API Key de OpenAI en la barra lateral para comenzar.")
            return
        
        try:
            client = openai.OpenAI(api_key=st.session_state.api_key)
            self.handle_file_upload(client)
            self.handle_chat(client)
        except Exception as e:
            st.error(f"Error en la aplicación: {str(e)}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = StudyBuddyApp()
    app.run()