"""
Test the CustomPythonREPLTool implementation
"""

import sys
import os

# Add the project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))
from src.services.custom_llm.utils.python_repl import CustomPythonREPLTool

def main():
    """Test the CustomPythonREPLTool with a simple example."""
    
    # Initialize the tool
    repl_tool = CustomPythonREPLTool()
    
    # Create a test DataFrame
    test_code = """
import pandas as pd
import numpy as np

# Create a simple DataFrame
df = pd.DataFrame({
    'A': [1, 2, 3, 4, 5],
    'B': [10, 20, 30, 40, 50],
    'C': ['a', 'b', 'c', 'd', 'e']
})

# Perform some calculations
result = df['A'].sum()
print(f"Sum of column A: {result}")

# Calculate mean of column B
mean_b = df['B'].mean()
print(f"Mean of column B: {mean_b}")

# Filter the DataFrame
filtered_df = df[df['A'] > 2]
print("Filtered DataFrame:")
print(filtered_df)
"""
    
    # Run the code
    output = repl_tool.run(test_code)
    
    print("=== Output from CustomPythonREPLTool ===")
    print(output)
    print("=======================================")
    
    # Test error handling
    error_code = """
# This will cause an error
x = 10 / 0
"""
    
    output = repl_tool.run(error_code)
    
    print("=== Error handling test ===")
    print(output)
    print("==========================")

if __name__ == "__main__":
    main()
