import logging
from typing import Optional, Dict, Any
import pandas as pd
from src.constants.llm_constant import AZURE_LLM00
from src.services.custom_llm.services.table_analysis import TableAnalysisService

logger = logging.getLogger(__name__)


class TableAnalysisController:
    """
    Handles the process of analyzing a Pandas DataFrame based on a user question
    using an LLM, including data normalization, prompt generation, LLM interaction,
    code execution, and a retry mechanism for handling errors.
    """

    MAX_RETRIES = 2

    @staticmethod
    def post(
        df: pd.DataFrame, question: str, df_name: str = "df", topic: str = "General Data Analysis"
    ) -> Dict[str, Any]:
        """
        Analyzes the provided DataFrame based on the user's question.

        Args:
            df: The Pandas DataFrame to analyze.
            question: The user's question about the DataFrame.
            df_name: The variable name to use for the DataFrame in the generated code.
            topic: The general topic or context of the data analysis.

        Returns:
            A dictionary containing:
            - 'python_code' (str): The generated Python code if successful, or an error code string.
            - 'result' (str): The standard output from the executed Python code if successful,
                              or a descriptive error message if analysis failed.
        """
        attempts = 0
        last_error_info: Optional[Dict] = None
        final_result: str = f"Error: Analysis failed after {TableAnalysisController.MAX_RETRIES + 1} attempts."
        python_code: str = "N/A"  # Default status code

        try:
            llm = AZURE_LLM00
            service = TableAnalysisService()
            # normalized_df = service.normalize_data(df.copy())
            normalized_df = df.copy()
        except Exception as e:
            logger.exception(f"Fatal Error during initialization or normalization: {str(e)}")
            return {"python_code": "INIT_OR_NORM_ERROR", "result": f"Initialization or Normalization failed: {str(e)}"}

        while attempts <= TableAnalysisController.MAX_RETRIES:
            try:
                prompt = service.generate_prompt(normalized_df, question, df_name, last_error_info, topic)
                response = llm.invoke(prompt)
                response_content = getattr(response, "content", str(response))

                result_or_error_msg, status_code, error_for_retry = service.handle_llm_response(
                    question, response_content, normalized_df, df_name
                )

                final_result = result_or_error_msg
                python_code = status_code
                last_error_info = error_for_retry

                if error_for_retry is None:
                    # Success, no need to retry
                    break
                # else: Error occurred, loop will continue if attempts remain

            except Exception as e:
                logger.exception(f"Unexpected error during attempt {attempts + 1}: {str(e)}")
                last_error_info = {"code": "CONTROLLER_EXCEPTION", "error": f"Unexpected controller error: {str(e)}"}
                final_result = last_error_info["error"]
                python_code = last_error_info["code"]

            attempts += 1

        return {"python_code": python_code, "result": final_result}
