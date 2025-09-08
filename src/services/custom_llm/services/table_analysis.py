import json
import re
from typing import Any  # Added Any for flexibility

import numpy as np
import pandas as pd

# Using our custom Python REPL implementation
from src.services.custom_llm.utils.python_repl import CustomPythonREPLTool


class TableAnalysisService:
    """Provides services for analyzing a Pandas DataFrame using an LLM.

    This includes generating prompts with DataFrame context and error information,
    parsing LLM responses, executing generated Python code safely,
    and normalizing input DataFrames.
    """

    def __init__(self):
        """Initializes the service with the base prompt template and Python REPL tool."""
        # Using the improved prompt template
        self.base_prompt_template = """Analyze the DataFrame '{df_name}' based on the user question.
Data_Context: {topic}
Input Schema:
{sample_data}
Columns: {columns}
Data Types:
{dtypes}

User Question: {question}

Analysis Guidelines:
1. Use ONLY columns listed: {columns}. Always check existence ('col' in {df_name}.columns).
2. Generate MINIMAL Python code using pandas for the analysis. Use '{df_name}' as the DataFrame variable.
3. Handle missing data appropriately (.fillna(0), .dropna()). Use vectorized operations.
4. Output results using print() with clear formatting.
5. Pay careful attention to INDENTATION in your code - ensure all code blocks are properly indented.
6. Use `.loc[row_indexer, col_indexer] = value` when assigning values to slices of DataFrames to
 avoid `SettingWithCopyWarning`.

DATA HANDLING PATTERNS:
- FILTERS: Use boolean masks (df[mask]) for filtering data.

DATE HANDLING STRATEGY:
1. IDENTIFY relevant date columns from {columns} based on names/patterns.
   - **Prioritize columns named like 'Date', 'Day and Date', 'Ngày', 'Timestamp'.**
   - Use the identified primary date column for general date parsing and analysis unless the question directs otherwise.
2. PARSE dates robustly from the identified primary date column using pd.to_datetime(..., errors='coerce').
3. CALCULATE durations based on question intent, using the parsed dates:
   - For TOTAL continuous days: (end_date - start_date).dt.days + 1
   - For WEEKDAY only (Mon-Fri): Use numpy.busday_count() **(Remember to import numpy as np)**.
4. HANDLE NaT values explicitly in filtering (e.g., `df['parsed_start_date'].notna()`) and aggregations.

COMMON DATE PARSING PATTERN (Reference logic - adjust indentation and column names in your code):
# Function to parse date column with ranges or single dates
def parse_date_column(date_input):
    if pd.isna(date_input):
        return pd.NaT, pd.NaT
    date_str = str(date_input).strip()
    if re.search(r'\\bto\\b', date_str, flags=re.IGNORECASE):
        parts = re.split(
            r'\\s*(?:\\bfrom\\b\\s+)?(.*?)?\\s+\\bto\\b\\s+(.*)',
            date_str,
            flags=re.IGNORECASE | re.DOTALL
        )
        parts = [p.strip() for p in parts if p and p.strip()]
        if len(parts) >= 2:
            start_str = re.sub(r'^\\w+,\\s*', '', parts[0]).strip()
            end_str = re.sub(r'^\\w+,\\s*', '', parts[-1]).strip()
            return pd.to_datetime(start_str, errors='coerce'), pd.to_datetime(end_str, errors='coerce')
    cleaned_str = re.sub(r"\\(.*\\)", "", date_str).strip()
    cleaned_str = re.sub(r'^\\w+,\\s*', '', cleaned_str).strip()
    single_date = pd.to_datetime(cleaned_str, errors='coerce')
    return single_date, single_date

# Applying the function (example using placeholder names)
# primary_date_col = 'actual_date_column_name'
# result = {df_name}[primary_date_col].apply(parse_date_column)
# {df_name}['parsed_start_date'] = result.apply(lambda x: x[0])
# {df_name}['parsed_end_date'] = result.apply(lambda x: x[1])

ERROR PREVENTION:
- Double-check all code indentation before returning results.
- Don't create the DataFrame (it already exists as '{df_name}').
- Don't assume date formats without parsing using `pd.to_datetime`.
- Explicitly handle missing data (`NaT`, `NaN`).
- Use only columns listed in: {columns}.
- Ensure you are parsing the **correct date column** based on the question's intent and the `DATE HANDLING STRATEGY`.
- Filter `NaT` values in date comparisons and calculations where appropriate.
- Use `.loc` for assignments on DataFrame slices.

{error_section}

Output: Return ONLY a valid JSON object with keys 'code' (string, containing Python code or an error code:
'NOT_AN_ANALYSIS_QUESTION', 'IRRELEVANT_QUESTION', 'UNKNOWN_ANSWER') and
'error' (string, empty on success, or explains the error code).
"""
        self.llm_error_codes = [
            "NOT_AN_ANALYSIS_QUESTION",
            "IRRELEVANT_QUESTION",
            "UNKNOWN_ANSWER",
        ]
        self.repl_tool = CustomPythonREPLTool()

    def _vectorized_is_note_row(self, df: pd.DataFrame) -> pd.Series:
        """Identifies rows likely containing unstructured notes or headers using vectorized operations.

        Args:
            df: The DataFrame to check.

        Returns:
            A boolean Series where True indicates a likely note row.

        """
        if df.empty:
            return pd.Series([False] * len(df), index=df.index)

        df_str = df.astype(str)
        note_keywords_pattern = (
            r"note|in case|employee|public holiday|compensatory|time-off|depending on|company|following the situation"
        )

        # Check 1: Long cells containing specific keywords
        long_cells_contain_keyword = df_str.apply(
            lambda col: col.str.contains(note_keywords_pattern, case=False, na=False) & (col.str.len() > 100),
            axis=0,
        )
        keyword_check = long_cells_contain_keyword.any(axis=1)

        # Check 2: Rows with multiple long cells
        long_text_count_per_row = (df_str.apply(lambda col: col.str.len() > 50, axis=0)).sum(axis=1)
        long_text_check = long_text_count_per_row >= 3

        # Check 3: Rows where all non-NA cells have identical, long content
        def check_identical_long(row):
            vals = row.dropna().astype(str)
            # Skip rows with NaNs or empty rows
            if len(vals) == 0 or len(vals) != len(row):
                return False
            first_val = vals.iloc[0]
            return (vals == first_val).all() and len(first_val) > 50

        if len(df.columns) > 0:
            identical_content_check = df.apply(check_identical_long, axis=1)
        else:
            identical_content_check = pd.Series([False] * len(df), index=df.index)

        # Combine checks
        is_note = keyword_check | long_text_check | identical_content_check
        return is_note

    def detect_and_remove_confluence_notes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detects and removes rows identified as likely notes or headers.

        Args:
            df: The input DataFrame.

        Returns:
            A DataFrame with note rows removed.

        """
        if df.empty or len(df.columns) == 0:
            return df
        is_note_mask = self._vectorized_is_note_row(df)
        rows_to_keep_mask = ~is_note_mask
        # Use .loc for filtering and copying to avoid SettingWithCopyWarning
        return df.loc[rows_to_keep_mask].copy()

    def get_dataframe_info(self, df: pd.DataFrame, df_name: str = "df") -> dict[str, str]:
        """Extracts schema information and sample data from the DataFrame.

        Args:
            df: The DataFrame.
            df_name: The name used for the DataFrame.

        Returns:
            A dictionary containing DataFrame name, columns, data types, and sample data.

        """
        sample_data = df.head().to_markdown(index=False)
        return {
            "df_name": df_name,
            "columns": ", ".join(df.columns),
            "dtypes": "\n".join([f"- {col}: {dtype}" for col, dtype in df.dtypes.items()]),
            "sample_data": sample_data,
        }

    def generate_prompt(
        self,
        df: pd.DataFrame,
        question: str,
        df_name: str = "df",
        previous_error: dict | None = None,
        topic: str = "General Data Analysis",
    ) -> str:
        """Generates the full prompt string for the LLM.

        Args:
            df: The DataFrame to be analyzed.
            question: The user's question.
            df_name: The name of the DataFrame variable.
            previous_error: Optional error information from the last attempt.
            topic: The general topic of the analysis.

        Returns:
            The formatted prompt string.

        """
        df_info = self.get_dataframe_info(df, df_name)
        error_section = ""
        if previous_error:
            error_code = previous_error.get("code", "N/A")
            error_msg = previous_error.get("error", "Unknown error")
            error_section = (
                f"Retry Instruction: Previous attempt failed. Error code was {error_code}. "
                f"Error msg was: {error_msg}. Generate correct code."
            )
        else:
            error_section = "Generate Python code for the analysis."
        format_args = {
            "question": question,
            "error_section": error_section,
            "topic": topic,
            **df_info,
        }
        # Assuming the template and df_info keys are correct, KeyError shouldn't happen
        return self.base_prompt_template.format(**format_args)

    def parse_llm_response(self, response_content: str) -> tuple[str | None, str | None, str | None]:
        """Parses the LLM's JSON response string.

        Args:
            response_content: The raw response string from the LLM.

        Returns:
            A tuple containing:
            - code (Optional[str]): The extracted Python code string, or None on error.
            - error (Optional[str]): The extracted error message from the LLM JSON, or None.
            - parsing_error (Optional[str]): A description of the parsing/validation error, or None on success.

        """
        try:
            # Remove potential markdown code fences
            response_content = re.sub(r"^```json\s*|\s*```$", "", response_content, flags=re.MULTILINE).strip()
            data = json.loads(response_content)
            code = data.get("code")
            error = data.get("error")
            # Basic validation
            if not isinstance(code, str) or not isinstance(error, str):
                raise ValueError("Invalid JSON structure: 'code' and 'error' must be strings.")
            return code, error, None
        except ValueError as e:
            parsing_error_msg = f"Error parsing/validating LLM response: {e!s} - Response: {response_content[:200]}..."
            return None, None, parsing_error_msg

    def execute_generated_code(self, code: str, df: pd.DataFrame, df_name: str = "df") -> tuple[str, str]:
        """Executes the generated Python code in a safe environment using PythonREPLTool.

        Args:
            code: The Python code string generated by the LLM.
            df: The DataFrame to be used in the execution context.
            df_name: The variable name assigned to the DataFrame in the execution context.

        Returns:
            A tuple containing:
            - result (str): The standard output from the executed code, or "No output".
            - error_message (str): An error message string if execution failed, otherwise an empty string.

        """
        code_lines = code.split("\n")
        # Filter out any DataFrame re-creation attempts by the LLM
        filtered_code = "\n".join(
            line
            for line in code_lines
            if not line.strip().startswith("data =") and not line.strip().startswith(f"{df_name} = pd.DataFrame")
        )

        try:
            # Setup the execution environment
            setup_code = "import pandas as pd\nimport numpy as np\nnan = float('nan')\nimport re\n"
            # Reconstruct the DataFrame within the REPL environment
            df_dict_repr = df.to_dict(orient="list")
            setup_code += f"{df_name} = pd.DataFrame.from_dict({df_dict_repr})\n"
            full_code = f"{setup_code}\n{filtered_code}"

            # Execute using the REPL tool
            result = self.repl_tool.run(full_code)
            return result.strip() if result else "No output", ""

        except Exception as e:
            error_message = str(e)
            # Categorize common errors for better retry instructions
            if "ValueError: All arrays must be of the same length" in error_message:
                return "", f"DATAFRAME_RECONSTRUCTION_ERROR: {error_message}"
            if "KeyError" in error_message:
                # Extract the missing key if possible for more specific feedback
                match = re.search(r"KeyError: '([^']*)'", error_message)
                key = match.group(1) if match else "unknown"
                return (
                    "",
                    f"IRRELEVANT_QUESTION: Code referenced a missing column: '{key}' - {error_message}",
                )
            if "SyntaxError" in error_message:
                return (
                    "",
                    f"CODE_SYNTAX_ERROR: Generated code has syntax errors - {error_message}",
                )
            # Catch-all for other execution errors
            return "", f"CODE_EXECUTION_ERROR: {error_message}"

    def handle_llm_response(
        self,
        question: str,
        response_content: str,
        df: pd.DataFrame,
        df_name: str = "df",
    ) -> tuple[str, str, dict[str, Any] | None]:
        """Processes the LLM response, executes code, and determines the final outcome.

        Args:
            question: The original user question.
            response_content: The raw response string from the LLM.
            df: The DataFrame used for analysis.
            df_name: The name of the DataFrame variable.

        Returns:
            A tuple containing:
            - result_or_error_msg (str): The execution result or a descriptive error message.
            - status_code (str): The Python code (on success) or an error code string.
            - error_for_retry (Optional[Dict]): Error details if retry is needed, else None.

        """
        code, llm_error, parsing_error = self.parse_llm_response(response_content)

        if parsing_error:
            error_info = {"code": "INVALID_JSON", "error": parsing_error}
            return parsing_error, "INVALID_JSON", error_info

        # Check if LLM returned a specific non-executable code (e.g., question irrelevant)
        if code in self.llm_error_codes:
            return llm_error or f"Analysis determined as: {code}", code, None

        if not code:
            error_info = {
                "code": "MISSING_CODE",
                "error": "LLM response JSON missing 'code' field.",
            }
            return (
                "Error: LLM response missing 'code' field.",
                "MISSING_CODE",
                error_info,
            )

        # Attempt to execute the valid code string
        execution_result, execution_error_msg = self.execute_generated_code(code, df, df_name)

        if execution_error_msg:
            # Execution failed, prepare details for potential retry
            error_info = {"code": code, "error": execution_error_msg}
            return execution_error_msg, "CODE_EXECUTION_FAILED", error_info
        # Execution successful
        return execution_result, code, None

    def normalize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies normalization steps to the DataFrame before analysis.

        Steps include removing potential note rows, stripping whitespace
        from object columns, and replacing empty strings resulting from stripping
        with NaN.

        Args:
            df: The input DataFrame.

        Returns:
            The normalized DataFrame.

        """
        # df = self.detect_and_remove_confluence_notes(df)  # noqa: ERA001

        for col in df.select_dtypes(include=["object"]).columns:
            # Combine stripping and empty string replacement in one apply call
            def normalize_and_nan_empty(x):
                if pd.isna(x):
                    return np.nan  # Keep existing NaNs
                # Convert to string, strip whitespace
                stripped_val = str(x).strip()
                # Return NaN if the stripped value is empty, otherwise return the stripped value
                return np.nan if stripped_val == "" else stripped_val

            # Assign the final result once per column
            df.loc[:, col] = df[col].apply(normalize_and_nan_empty)
        return df
