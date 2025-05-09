import asyncio
import json
import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from agents import Agent, Runner, function_tool
from typing import List
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Set model choice
model = os.getenv('LLM_MODEL_NAME', 'gpt-4o-mini')

# Initialize FastAPI app
app = FastAPI(title="Fitness Coach API")

# Add CORS middleware to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (update for production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Structured Output Models ---
class WorkoutPlan(BaseModel):
    """Workout recommendation with exercises and details"""
    focus_area: str = Field(description="Primary focus of the workout (e.g., 'upper body', 'cardio')")
    difficulty: str = Field(description="Difficulty level (Beginner, Intermediate, Advanced)")
    exercises: List[str] = Field(description="List of recommended exercises")
    notes: str = Field(description="Additional notes or form tips")

class MealPlan(BaseModel):
    """Basic meal plan recommendation"""
    daily_calories: int = Field(description="Recommended daily calorie intake")
    protein_grams: int = Field(description="Daily protein target in grams")
    carbs_grams: int = Field(description="Daily carbohydrate target in grams") 
    fat_grams: int = Field(description="Daily fat target in grams")
    meal_suggestions: List[str] = Field(description="Simple meal ideas")
    notes: str = Field(description="Dietary advice and tips")

# --- Request Models ---
class GeneralQueryRequest(BaseModel):
    query: str = Field(description="General fitness query")

class WorkoutQueryRequest(BaseModel):
    muscle_group: str = Field(description="Target muscle group (e.g., chest, legs)")
    level: str = Field(description="Fitness level (Beginner, Intermediate, Advanced)")

class NutritionQueryRequest(BaseModel):
    goal: str = Field(description="Fitness goal (weight loss, muscle gain, maintenance)")
    weight_kg: float = Field(description="Weight in kilograms")
    height_cm: float = Field(description="Height in centimeters")
    age: int = Field(description="Age in years")
    gender: str = Field(description="Gender (male, female)")

# --- Tools ---
@function_tool
def get_exercise_info(muscle_group: str) -> str:
    """Get a list of exercises for a specific muscle group"""
    logger.debug(f"Calling get_exercise_info with muscle_group: {muscle_group}")
    exercise_data = {
        "chest": [
            "Push-ups: 3 sets of 10-15 reps",
            "Bench Press: 3 sets of 8-12 reps",
            "Chest Flyes: 3 sets of 12-15 reps",
            "Incline Push-ups: 3 sets of 10-15 reps"
        ],
        "back": [
            "Pull-ups: 3 sets of 6-10 reps",
            "Bent-over Rows: 3 sets of 8-12 reps",
            "Lat Pulldowns: 3 sets of 10-12 reps",
            "Superman Holds: 3 sets of 30 seconds"
        ],
        "legs": [
            "Squats: 3 sets of 10-15 reps",
            "Lunges: 3 sets of 10 per leg",
            "Calf Raises: 3 sets of 15-20 reps",
            "Glute Bridges: 3 sets of 15 reps"
        ],
        "arms": [
            "Bicep Curls: 3 sets of 10-12 reps",
            "Tricep Dips: 3 sets of 10-15 reps",
            "Hammer Curls: 3 sets of 10-12 reps",
            "Overhead Tricep Extensions: 3 sets of 10-12 reps"
        ],
        "core": [
            "Planks: 3 sets of 30-60 seconds",
            "Crunches: 3 sets of 15-20 reps",
            "Russian Twists: 3 sets of 20 total reps",
            "Mountain Climbers: 3 sets of 20 total reps"
        ]
    }
    
    muscle_group = muscle_group.lower()
    if muscle_group in exercise_data:
        exercises = exercise_data[muscle_group]
        result = {
            "muscle_group": muscle_group,
            "exercises": exercises,
            "recommendation": f"For {muscle_group} training, complete all exercises with 60-90 seconds rest between sets."
        }
        logger.debug(f"get_exercise_info result: {result}")
        return json.dumps(result)
    else:
        logger.warning(f"Muscle group {muscle_group} not found")
        return f"Exercise information for {muscle_group} is not available."

@function_tool
def calculate_calories(goal: str, weight_kg: float, height_cm: float, age: int, gender: str) -> str:
    """Calculate daily calorie needs and macronutrient breakdown based on user stats and goals"""
    logger.debug(f"Calling calculate_calories with goal: {goal}, weight_kg: {weight_kg}, height_cm: {height_cm}, age: {age}, gender: {gender}")
    
    # Calculate BMR (Basal Metabolic Rate) using Mifflin-St Jeor Equation
    if gender.lower() in ['male', 'm']:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:  # female
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
    
    # Use a moderate activity level
    tdee = bmr * 1.55
    
    # Adjust based on goal
    if goal.lower() == "weight loss":
        calorie_target = tdee - 500
    elif goal.lower() == "muscle gain":
        calorie_target = tdee + 300
    else:
        calorie_target = tdee
    
    # Calculate macros
    if goal.lower() == "weight loss":
        protein_pct, fat_pct, carb_pct = 0.40, 0.30, 0.30
    elif goal.lower() == "muscle gain":
        protein_pct, fat_pct, carb_pct = 0.30, 0.25, 0.45
    else:
        protein_pct, fat_pct, carb_pct = 0.30, 0.30, 0.40
    
    protein_calories = calorie_target * protein_pct
    fat_calories = calorie_target * fat_pct
    carb_calories = calorie_target * carb_pct
    
    protein_grams = round(protein_calories / 4)
    fat_grams = round(fat_calories / 9)
    carb_grams = round(carb_calories / 4)
    
    result = {
        "goal": goal,
        "daily_calories": round(calorie_target),
        "macros": {
            "protein": protein_grams,
            "fat": fat_grams,
            "carbs": carb_grams
        }
    }
    
    logger.debug(f"calculate_calories result: {result}")
    return json.dumps(result)

# --- Specialized Agents ---
workout_agent = Agent(
    name="Workout Specialist",
    handoff_description="Specialist agent for creating workout plans",
    instructions="""
    You are a workout specialist who creates effective exercise routines.
    Use the get_exercise_info tool to find exercises for specific muscle groups.
    Create a WorkoutPlan that matches the user's fitness level and goals.
    For weight loss, include a mix of cardio and strength exercises.
    Always include form tips in the notes to prevent injury.
    Ensure the output strictly follows the WorkoutPlan schema.
    """,
    model=model,
    tools=[get_exercise_info],
    output_type=WorkoutPlan
)

nutrition_agent = Agent(
    name="Nutrition Specialist",
    handoff_description="Specialist agent for nutrition advice and meal planning",
    instructions="""
    You are a nutrition specialist who helps users with meal planning and nutrition advice.
    Use the calculate_calories tool to determine appropriate calorie and macronutrient targets.
    Provide a MealPlan with meal suggestions that support the user's fitness goals.
    Focus on practical, sustainable nutrition advice.
    Ensure the output strictly follows the MealPlan schema.
    """,
    model=model,
    tools=[calculate_calories],
    output_type=MealPlan
)

# --- Main Fitness Agent ---
fitness_agent = Agent(
    name="Fitness Coach with Specialized Agents",
    instructions="""
    You are a fitness coach who helps users achieve their health and fitness goals.
    For queries about workouts or exercises, immediately hand off to the Workout Specialist.
    For queries about nutrition, diet, or meal plans, immediately hand off to the Nutrition Specialist.
    For general fitness questions, provide brief, practical advice without using tools or handoffs.
    Do not attempt to answer specialized workout or nutrition questions yourself.
    """,
    model=model,
    tools=[get_exercise_info, calculate_calories],
    handoffs=[workout_agent, nutrition_agent]
)

# --- API Endpoints ---
@app.post("/fitness/general", response_model=dict)
async def general_fitness_query(request: GeneralQueryRequest):
    try:
        logger.info(f"Processing general fitness query: {request.query}")
        result = await Runner.run(fitness_agent, request.query, max_turns=20)
        return {"response": result.final_output}
    except Exception as e:
        logger.error(f"Error processing general query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fitness/workout", response_model=WorkoutPlan)
async def workout_query(request: WorkoutQueryRequest):
    try:
        query = f"Create a workout plan for {request.muscle_group} at {request.level} level"
        logger.info(f"Processing workout query: {query}")
        result = await Runner.run(workout_agent, query, max_turns=20)
        return result.final_output
    except Exception as e:
        logger.error(f"Error processing workout query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/fitness/nutrition", response_model=MealPlan)
async def nutrition_query(request: NutritionQueryRequest):
    try:
        query = f"Create a meal plan for {request.goal} with weight {request.weight_kg}kg, height {request.height_cm}cm, age {request.age}, gender {request.gender}"
        logger.info(f"Processing nutrition query: {query}")
        result = await Runner.run(nutrition_agent, query, max_turns=20)
        return result.final_output
    except Exception as e:
        logger.error(f"Error processing nutrition query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)