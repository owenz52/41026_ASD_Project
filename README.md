# 41026_ASD_Project
This project simulates a student dashboard allowing them to view and organise their subjects. Each feature is a microservices with their own frontend, backend and database. Additioanlly each feature have a AI feature that uses a local Ollama model(QWEN) to generate responses.

Features:
Register, Login, Enrolment, Calendar, Notebook, Assessment and Exam Tracker 

Application Requirements: 
Docker , Ollama with qwen2.5:0.5b

Setup steps:
// Within the docker-compose.yml file, the ports need to changed if already used by other systems.
1. CD to project file
2. Run "docker compose up --build" in terminal
3. Open http://localhost:8000/ in web browser
4. To stop container use Ctrl + C
5. To remove the container use "docker compose down", "docker compose down -v" to remove volumns
