import asyncio
import logging
from datetime import datetime

import pandas as pd
import psycopg

from src.config.settings import (
    postgres_db_host,
    postgres_db_name_autotest,
    postgres_db_password,
    postgres_db_port,
    postgres_db_user,
)
from src.services.jira_services.services.jira_utils import process_llm_prompt
from src.services.postgres.db_utils import get_db
from src.services.rag_services.services.dynamic_rag_service import DynamicRagService

_logger = logging.getLogger(__name__)
# Number of test iterations per question
NUM_TESTS = 3
# Number of concurrent workers for processing rows
NUM_WORKERS = 2


def load_config() -> dict:
    """Load PostgresSQL database configuration from settings."""
    return {
        "host": postgres_db_host,
        "port": postgres_db_port,
        "dbname": postgres_db_name_autotest,
        "user": postgres_db_user,
        "password": postgres_db_password,
    }


def initialize_database_connection() -> psycopg.Connection:
    """Initialize a connection to the PostgreSQL database."""
    return psycopg.connect(**load_config())


# Main function to process a DataFrame with AI and return results
async def process_file_with_ai(df_process: pd.DataFrame, rag_source: str, processed_filename: str) -> tuple:
    """Process a DataFrame with AI and return results."""
    df = df_process.copy()  # Initialize variables for tracking progress and results
    total_questions = len(df)
    current_time = datetime.now()
    total_answers = total_questions * NUM_TESTS
    accuracy = 0.0
    test_type = rag_source
    status = "processing"

    connection = initialize_database_connection()
    # Insert info file to DB
    record_id = insert_initial_record(
        connection,
        current_time,
        total_questions,
        total_answers,
        accuracy,
        test_type,
        status,
        processed_filename,
    )

    # Add columns for dataframe
    for i in range(1, NUM_TESTS + 1):
        df[f"Answer {i}"] = ""
        df[f"Test {i}"] = 0.0
    df["Total"] = 0.0

    _logger.info("Processing Test RAG.")

    # Function to process a single row of the DataFrame
    async def process_row(index: int, row: pd.Series) -> None:
        try:
            question = str(row["Question"]).strip()
            dic = {
                "Question": question,
                "Correct Answer": str(row["Correct Answer"]).strip(),
            }  # Use the RAG function with the provided rag_source
            for i in range(1, NUM_TESTS + 1):
                ai_response = await make_rag_request(question, rag_source)
                dic[f"Test {i}"] = ai_response
                df.at[index, f"Answer {i}"] = ai_response

            # Compare AI responses with the correct answer using an LLM
            answers = await compare_with_ai(dic)
            if answers:
                results = [line.split(": ")[1].strip() for line in answers.strip().split("\n")]
                percentages = []
                for i in range(1, NUM_TESTS + 1):
                    if i <= len(results):
                        percentage = float(results[i - 1].rstrip("%"))
                        percentages.append(percentage)
                        df.at[index, f"Test {i}"] = percentage

                # Calculate and store the average accuracy for the row
                if percentages:
                    average_accuracy = sum(percentages) / len(percentages)
                    df.at[index, "Total"] = round(average_accuracy, 2)
                else:
                    df.at[index, "Total"] = 0.0

        except Exception as e:
            _logger.error("Error processing row %s: %s", index, str(e))
            df.at[index, "Total"] = 0.0

    # Process rows concurrently
    tasks = [process_row(int(idx), row) for idx, row in df.iterrows()]
    await asyncio.gather(*tasks, return_exceptions=True)

    # Calculate the overall average accuracy across all questions
    total_accuracy_sum = df["Total"].sum()
    average_accuracy = (total_accuracy_sum / total_questions) if total_questions > 0 else 0.0
    average_accuracy = round(average_accuracy, 2)
    df.at[0, "Average accuracy (%)"] = round(average_accuracy, 2)

    # Prepare statistics for the response
    stats = {
        "total_questions": total_questions,
        "average_accuracy": average_accuracy,
    }

    # Update the database record with the final accuracy and status
    update_record(connection, record_id, average_accuracy, "success")
    close_connection(connection)

    return df, stats


# Insert an initial record into the database and return its ID
def insert_initial_record(
    connection: psycopg.Connection,
    current_time: datetime,
    total_questions: int,
    total_answers: int,
    accuracy: float,
    test_type: str,
    status: str,
    processed_filename: str,
) -> int:
    """Insert a new record into the database and return its ID."""
    insert_query = """
        INSERT INTO rag_test_results (time, total_questions, total_answers, accuracy, test_type, status, filename)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                insert_query,
                (
                    current_time,
                    total_questions,
                    total_answers,
                    accuracy,
                    test_type,
                    status,
                    processed_filename,
                ),
            )
            connection.commit()
            return cursor.fetchone()[0]
    except psycopg.Error as e:
        connection.rollback()
        raise psycopg.Error(f"Failed to insert initial record: {e}") from e


# Function to safely close a database connection
def close_connection(connection: psycopg.Connection) -> None:
    """Close the database connection if it is open."""
    if connection is not None:
        try:
            if not connection.closed:
                connection.close()
        except Exception as e:
            _logger.error("Error closing database connection: %s", e)


# Update an existing record in the database with final accuracy and status
def update_record(connection: psycopg.Connection, record_id: int, accuracy: float, status: str) -> None:
    """Update the accuracy and status of a test record."""
    update_query = """
        UPDATE rag_test_results 
        SET accuracy = %s, status = %s 
        WHERE id = %s;
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(update_query, (accuracy, status, record_id))
            connection.commit()
            _logger.info(f"Updated record ID: {record_id}")
    except psycopg.Error as e:
        connection.rollback()
        raise psycopg.Error(f"Failed to update record ID {record_id}: {e}") from e


# Direct function to make a RAG request using DynamicRagService
async def make_rag_request(question: str, rag_source: str) -> str:
    """Make a RAG request to the specified source."""
    try:
        # Create a database session using get_db
        db = next(get_db())

        # Initialize DynamicRagService with the rag_source
        rag_service = DynamicRagService(collection_name=rag_source)

        # Make the direct call to ask_with_no_memory
        response = await rag_service.ask_with_no_memory(question=question, db=db, analyze_mode=False)
        return response
    except Exception as e:
        _logger.error("Error in make_rag_request: %s", e)
        return f"Error: {str(e)}"


# Compare AI-generated answers with the correct answer using an LLM
async def compare_with_ai(dic: dict) -> str | None:
    """Compare AI-generated answers with the correct answer."""
    try:
        prompt = "\n".join(
            [
                "Analyze the test results against the correct answer for the following question:",
                f"Question: {dic['Question']}",
                f"Correct Answer: {dic['Correct Answer']}",
                "Test Results:",
                *[f"- Test {i}: {dic[f'Test {i}']}" for i in range(1, NUM_TESTS + 1)],
                "Compare each test result with the correct answer. For each test result, calculate the percentage of accuracy (0-100%).",
                "Return only: Test 1: X%Test 2: X%Test 3: X%",
            ]
        )
        response = await process_llm_prompt(prompt)
        return str(response)
    except Exception as e:
        _logger.error("Error in compare_with_ai: %s", e)
        return None
