from typing import List, Optional
from teams.state import UserState

class EnhancedUserState(UserState):
    """
    Extended UserState with question history tracking
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.question_history: List[str] = kwargs.get("question_history", [])
        
    def add_question(self, question: str, max_history: int = 10) -> None:
        """
        Add a new question to the user's history
        
        Args:
            question: The question text to store
            max_history: Maximum number of questions to maintain (oldest will be removed)
        """
        self.question_history.append(question)
        
        # Trim history if it exceeds max_history
        if len(self.question_history) > max_history:
            self.question_history = self.question_history[-max_history:]