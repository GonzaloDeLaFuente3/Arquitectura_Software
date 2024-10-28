# Importaciones
from openai import OpenAI
import os
from dotenv import load_dotenv
import time
import logging
from datetime import datetime
import requests
import json
import streamlit as st

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Obtener las claves API
news_api_key = os.environ.get("NEWS_API_KEY")
openai_api_key = os.environ.get("OPENAI_API_KEY")

# Verificar que las claves existen
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY no está configurada en el archivo .env")
if not news_api_key:
    raise ValueError("NEWS_API_KEY no está configurada en el archivo .env")

# Crear el cliente OpenAI
try:
    client = OpenAI(api_key=openai_api_key)
    model = "gpt-3.5-turbo"
except Exception as e:
    print(f"Error al crear el cliente OpenAI: {e}")
    raise


#Conecta con la API de noticias
# Obtiene 5 artículos sobre un tema específico
# Procesa y formatea la información de cada artículo
def get_news(topic):
    url = (
        f"https://newsapi.org/v2/everything?q={topic}&apikey={news_api_key}&pageSize=5"
    )
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            new = json.dumps(response.json(), indent=4)
            news_json = json.loads(new)
            
            data = news_json
            
            #acceder a todos los campos
            status = data["status"]
            total_results = data["totalResults"]
            articles = data["articles"]
            final_news = []
            
            #recorro todo el bucle del articulo
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
            return []
            
    except requests.exceptions.RequestException as e:
        print("error ocurrido durante el API request", e)
        return []

# Mantiene IDs estáticos para el hilo y asistente
# Inicializa el cliente de OpenAI
class AssistantManager:
    thread_id = "thread_0Kj5wiLRKSqjFAsjKUoJ81KM"
    assistant_id = "asst_lGXfMK3d31Qw0NxlqdW45ILO" 
    
    def __init__(self, model:str =model):
        self.client = client
        self.model = model
        self.assistant = None  # Inicializado
        self.thread = None    # Inicializado
        self.run = None
        self.summary = None 
        
        # Verificar si existe asistente 
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
    #Interfaz Streamlit
    st.set_page_config(page_title="News Summarizer", page_icon="📰")
    
    try:
        manager = AssistantManager()

        st.title("📰 News Summarizer")
        st.markdown("Enter a topic to get a summary of the latest news about it.")
        
        with st.form(key="user_input_form"):
            instructions = st.text_input(
                "Enter topic:", 
                placeholder="Example: bitcoin, technology, sports..."
            )
            submit_button = st.form_submit_button(label="Get Summary")

            if submit_button and instructions:
                with st.spinner('Creating assistant and processing news...'):
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
                        content=f"summarize the news on this topic: {instructions}. Proporciona la informacion en español"
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
                st.warning("Please enter a topic first!")

    except Exception as e:
        st.error(f"An error occurred: {e}")
        raise

if __name__ == "__main__":
    main()