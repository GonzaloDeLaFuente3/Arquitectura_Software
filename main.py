from openai import OpenAI
import os
from dotenv import load_dotenv

import time 
import logging
from datetime import datetime

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Obtener la clave de API desde las variables de entorno
api_key = os.environ.get("OPENAI_API_KEY")


# Verificar si la clave se obtiene correctamente
if api_key is None:
    raise ValueError("La clave de API no está configurada. Verifica tu archivo .env.")

try:
    # Crear el cliente
    client = OpenAI(api_key=api_key)
    
    # # Crear el asistente
    # entrenador_personal_asistente = client.beta.assistants.create(
    #     name="Entrenador personal",
    #     instructions="Eres un asistente personal de fitness. Ayuda a crear un plan integral de entrenamiento y nutrición personalizado. Proporciona un plan de entrenamiento semanal que combine ejercicios de fuerza, cardio y estiramientos, y un plan nutricional diario. Responde siempre en español.",
    #     model="gpt-3.5-turbo"
    # )
    
    # # Imprimir el ID del asistente
    # print("ID del asistente:", entrenador_personal_asistente.id)
    #ID del asistente: asst_hN7NGZwrIpDEbXthNDOEancz
    asistente_id="asst_hN7NGZwrIpDEbXthNDOEancz"
    
    # # Crear un hilo
    #Thread: Una conversación continua entre usuario y asistente
    # thread = client.beta.threads.create(
    #     messages=[
    #         {
    #             "role": "user",
    #             "content": "Soy un estudiante que quiere perder grasa y ganar masa muscular, ¿cómo puedes ayudarme con esto?"
    #         }
    #     ]
    # )
    
    # # Imprimir el ID del hilo
    # print("ID del hilo:", thread.id)
    #ID del hilo: thread_8WxIUdXm6wT3iQujqLMENc9v
    hilo_id = "thread_8WxIUdXm6wT3iQujqLMENc9v"

except Exception as e:
    print(f"Ocurrió un error: {str(e)}")

# crear mensaje 
message = "que es lo que debo beber en un dia para obtener resultados"
message = client.beta.threads.messages.create(
    thread_id = hilo_id,
    role="user",
    content=message
)

#ejecutar nuestro asistente 
run = client.beta.threads.runs.create(
    thread_id = hilo_id,
    assistant_id = asistente_id,
    instructions = "Por favor actua como un entrenador personal famoso"
)

#Función de Espera y Monitoreo
def wait_for_run_completion(client, thread_id, run_id, sleep_interval=5):
    """

    Waits for a run to complete and prints the elapsed time.:param client: The OpenAI client object.
    :param thread_id: The ID of the thread.
    :param run_id: The ID of the run.
    :param sleep_interval: Time in seconds to wait between checks.
    """
    while True:
        try:
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
            if run.completed_at:
                elapsed_time = run.completed_at - run.created_at
                formatted_elapsed_time = time.strftime(
                    "%H:%M:%S", time.gmtime(elapsed_time)
                )
                print(f"Run completed in {formatted_elapsed_time}")
                logging.info(f"Run completed in {formatted_elapsed_time}")
                # Get messages here once Run is completed!
                messages = client.beta.threads.messages.list(thread_id=thread_id)
                last_message = messages.data[0]
                response = last_message.content[0].text.value
                print(f"Assistant Response: {response}")
                break
        except Exception as e:
            logging.error(f"An error occurred while retrieving the run: {e}")
            break
        logging.info("Waiting for run to complete...")
        time.sleep(sleep_interval)

# === corro ===
wait_for_run_completion(client=client, thread_id=hilo_id, run_id=run.id)

# ==== Steps --- Logs ==
run_steps = client.beta.threads.runs.steps.list(thread_id=hilo_id, run_id=run.id)
print(f"Steps---> {run_steps.data[0]}")