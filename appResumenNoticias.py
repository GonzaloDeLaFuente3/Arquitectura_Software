# Importaciones
from openai import OpenAI
import os
import time
import logging
from datetime import datetime
import requests
import json
import streamlit as st

def initialize_session_state():
    if 'openai_api_key' not in st.session_state:
        st.session_state.openai_api_key = ''
    if 'news_api_key' not in st.session_state:
        st.session_state.news_api_key = ''
    if 'client' not in st.session_state:
        st.session_state.client = None

def create_openai_client():
    if st.session_state.openai_api_key:
        try:
            st.session_state.client = OpenAI(api_key=st.session_state.openai_api_key)
            return True
        except Exception as e:
            st.error(f"Error al crear el cliente OpenAI: {e}")
            return False
    return False

def get_news(topic):
    if not st.session_state.news_api_key:
        st.error("Se requiere la API key de News")
        return []
        
    url = (
        f"https://newsapi.org/v2/everything?q={topic}&apikey={st.session_state.news_api_key}&pageSize=5"
    )
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            new = json.dumps(response.json(), indent=4)
            news_json = json.loads(new)
            
            data = news_json
            
            status = data["status"]
            total_results = data["totalResults"]
            articles = data["articles"]
            final_news = []
            
            for article in articles:
                source_name = article["source"]["name"]
                author = article["author"]
                title = article["title"]
                description = article["description"]
                url = article["url"]
                content = article["content"]
                title_description = f"""
                    Title: {title},
                    Author: {author},
                    Source: {source_name},
                    Description: {description},
                    URL: {url}
                """
                final_news.append(title_description)
            
            return final_news
        else:
            st.error("Error al obtener noticias. Verifica tu API key de News.")
            return []
            
    except requests.exceptions.RequestException as e:
        st.error(f"Error ocurrido durante el API request: {e}")
        return []

class AssistantManager:
    thread_id = "thread_0Kj5wiLRKSqjFAsjKUoJ81KM"
    assistant_id = "asst_lGXfMK3d31Qw0NxlqdW45ILO" 
    
    def __init__(self):
        if not st.session_state.client:
            raise ValueError("OpenAI client no inicializado")
        self.client = st.session_state.client
        self.model = "gpt-3.5-turbo"
        self.assistant = None
        self.thread = None
        self.run = None
        self.summary = None 
        
        if AssistantManager.assistant_id:
            self.assistant = self.client.beta.assistants.retrieve(
                assistant_id=AssistantManager.assistant_id
            )
        if AssistantManager.thread_id:
            self.thread = self.client.beta.threads.retrieve(
                thread_id=AssistantManager.thread_id
            )

    #Crea un asistente especializado en resumir noticias
    def create_assistant(self, name, instructions, tools):
        try:
            assistant_obj = self.client.beta.assistants.create(
                name=name,
                instructions=instructions,
                tools=tools,
                model=self.model
            )
            AssistantManager.assistant_id = assistant_obj.id
            self.assistant = assistant_obj
            print(f"AssisID:::{self.assistant.id}")
        except Exception as e:
            st.error(f"Error creating assistant: {e}")
            raise
    
    #Crea un nuevo hilo de conversación
    def create_thread(self):
        try:
            thread_obj = self.client.beta.threads.create()
            AssistantManager.thread_id = thread_obj.id
            self.thread = thread_obj
            print(f"ThreadID::: {self.thread.id}")
        except Exception as e:
            st.error(f"Error creating thread: {e}")
            raise
    
    #Añade mensajes al hilo
    def add_message_to_thread(self, role, content):
        if self.thread:
            try:
                self.client.beta.threads.messages.create(
                    thread_id=self.thread.id,
                    role=role,
                    content=content
                )
            except Exception as e:
                st.error(f"Error adding message to thread: {e}")
                raise
    
    #Ejecuta el asistente con instrucciones específicas
    def run_assistant(self, instructions):
        if self.thread and self.assistant:
            try:
                self.run = self.client.beta.threads.runs.create(
                    thread_id=self.thread.id,
                    assistant_id=self.assistant.id,
                    instructions=instructions
                )
            except Exception as e:
                st.error(f"Error running assistant: {e}")
                raise

    def process_message(self):
        if self.thread:
            try:
                messages = self.client.beta.threads.messages.list(
                    thread_id=self.thread.id
                )
                summary = []

                last_message = messages.data[0]
                role = last_message.role
                response = last_message.content[0].text.value
                summary.append(response)

                self.summary = "\n".join(summary)
                print(f"SUMMARY-----> {role.capitalize()}: ==> {response}")
            except Exception as e:
                st.error(f"Error processing message: {e}")
                raise

    #Implementa el sistema de function calling de OpenAI
    # Permite al asistente obtener noticias dinámicamente
    # Maneja la respuesta y la devuelve al asistente            
    def call_required_functions(self, required_actions):
        if not self.run:
            return
        tools_outputs = []

        try:
            for action in required_actions["tool_calls"]:
                func_name = action["function"]["name"]
                arguments = json.loads(action["function"]["arguments"])

                if func_name == "get_news":
                    output = get_news(topic=arguments["topic"])
                    print(f"STUFFFF;;;{output}")
                    final_str = ""
                    for item in output:
                        final_str += "".join(item)

                    tools_outputs.append({
                        "tool_call_id": action["id"],
                        "output": final_str
                    })
                else:
                    raise ValueError(f"Unknown function: {func_name}")
                    
            print("Submitting outputs back to the Assistant...")
            self.client.beta.threads.runs.submit_tool_outputs(
                thread_id=self.thread.id,
                run_id=self.run.id,
                tool_outputs=tools_outputs
            )
        except Exception as e:
            st.error(f"Error in function calling: {e}")
            raise

    def get_summary(self):
        return self.summary

    #Espera y maneja la respuesta del asistente
    def wait_for_completion(self):
        if self.thread and self.run:
            while True:
                try:
                    time.sleep(1)
                    run_status = self.client.beta.threads.runs.retrieve(
                        thread_id=self.thread.id,
                        run_id=self.run.id
                    )
                    print(f"RUN STATUS:: {run_status.model_dump_json(indent=4)}")

                    if run_status.status == "completed":
                        self.process_message()
                        break
                    elif run_status.status == "requires_action":
                        print("FUNCTION CALLING NOW...")
                        self.call_required_functions(
                            required_actions=run_status.required_action.submit_tool_outputs.model_dump()
                        )
                    elif run_status.status == "failed":
                        st.error("The assistant run failed")
                        break
                except Exception as e:
                    st.error(f"Error while waiting for completion: {e}")
                    raise
        
    def run_steps(self):
        try:
            run_steps = self.client.beta.threads.runs.steps.list(
                thread_id=self.thread.id,
                run_id=self.run.id
            )
            print(f"Run-Steps::: {run_steps}")
            return run_steps
        except Exception as e:
            st.error(f"Error getting run steps: {e}")
            raise


def main():
    st.set_page_config(page_title="News Summarizer", page_icon="📰")
    initialize_session_state()
    
    st.title("📰 News Summarizer")
    
    # Sección de configuración de API keys
    with st.sidebar:
        st.header("Configuración de API Keys")
        openai_api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=st.session_state.openai_api_key,
            help="Ingresa tu API key de OpenAI"
        )
        news_api_key = st.text_input(
            "News API Key",
            type="password",
            value=st.session_state.news_api_key,
            help="Ingresa tu API key de News API"
        )
        
        if st.button("Guardar API Keys"):
            st.session_state.openai_api_key = openai_api_key
            st.session_state.news_api_key = news_api_key
            if create_openai_client():
                st.success("API Keys guardadas y cliente OpenAI inicializado correctamente!")
            else:
                st.error("Error al inicializar el cliente OpenAI. Verifica tu API key.")

    # Verificar si las API keys están configuradas
    if not st.session_state.openai_api_key or not st.session_state.news_api_key:
        st.warning("Por favor, configura tus API keys en la barra lateral antes de continuar.")
        return

    st.markdown("Enter a topic to get a summary of the latest news about it.(Ingrese un tema para obtener un resumen de las últimas noticias sobre él.)")
    
    try:
        with st.form(key="user_input_form"):
            instructions = st.text_input(
                "Enter topic:", 
                placeholder="Example: bitcoin, technology, sports..."
            )
            submit_button = st.form_submit_button(label="Get Summary")

            if submit_button and instructions:
                if not st.session_state.client:
                    st.error("Cliente OpenAI no inicializado. Verifica tu API key.")
                    return
                    
                with st.spinner('Creating assistant and processing news...'):
                    manager = AssistantManager()
                    manager.create_assistant(
                        name="News Summarizer",
                        instructions="You are a personal article summarizer Assistant who knows how to take a list of article's titles and descriptions and then write a short summary of all the news articles. TODAS LAS RESPUESTAS DEBEN SER SIEMPRE EN ESPAÑOL, independientemente del idioma de los artículos originales.",
                        tools=[{
                            "type": "function",
                            "function": {
                                "name": "get_news",
                                "description": "Get the list of articles/news for the given topic",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "topic": {
                                            "type": "string",
                                            "description": "The topic for the news, e.g. bitcoin"
                                        }
                                    },
                                    "required": ["topic"]
                                }
                            }
                        }]
                    )
                    
                    manager.create_thread()
                    manager.add_message_to_thread(
                        role="user",
                        content=f"summarize the news on this topic: {instructions}. Proporciona la informacion y la respuesta en español"
                    )
                    manager.run_assistant(instructions="Summarize the news. La respuesta DEBE ser siempre en español.")
                    manager.wait_for_completion()
                    
                    summary = manager.get_summary()
                    if summary:
                        st.success("Summary generated successfully!")
                        st.markdown(summary)
                    else:
                        st.warning("No summary was generated. Please try again.")
            
            elif submit_button and not instructions:
                st.warning("Please enter a topic first!-¡Por favor ingresa un tema primero!")

    except Exception as e:
        st.error(f"An error occurred: {e}")
        raise

if __name__ == "__main__":
    main()