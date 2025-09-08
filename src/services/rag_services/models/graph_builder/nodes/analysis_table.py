import json
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import SystemMessage

from src.services.custom_llm.controllers.table_analysis_controller import TableAnalysisController


def analysis_table(can_analyze, human_message, dfs):
	"""
	Analyzes a list of dataframes and generates Python code for each table.

	Args:
		can_analyze (bool): A flag indicating whether analysis is allowed.
		human_message (str): A message provided by the user for context.
		dfs (list): A list of dataframes to be analyzed.

	Returns:
		dict: A dictionary containing the analysis results and generated Python code.
	"""
	node_response = dict(messages=[], analysis_results='')

	if not dfs or not can_analyze:
		return node_response

	try:
		if not dfs:
			return node_response

		# Generate Python code for each table
		with ThreadPoolExecutor() as executor:
			responses = executor.map(
				lambda df: TableAnalysisController.post(df, human_message), dfs
			)

		# Collect analysis results
		analysis_results = [
			{
				'result': response.get('result'),
				'code': response.get('python_code'),
			}
			for idx, (response, df) in enumerate(zip(responses, dfs)) if response
		]

		# Create a system message with analysis results
		if analysis_results:
			analysis_results = json.dumps(analysis_results, indent=4, ensure_ascii=False)
			system_message = SystemMessage(
				content=analysis_results
			)

			node_response['messages'] = [system_message]
			node_response['analysis_results'] = analysis_results
	except Exception as e:
		print(f"Error analyzing tables: {e}")

	return node_response
