"""Sequential Thinking implementation in Python"""
from typing import Optional, List, Dict
import json


class ThoughtData:
    """思考データ"""
    def __init__(
        self,
        thought: str,
        thought_number: int,
        total_thoughts: int,
        next_thought_needed: bool,
        is_revision: bool = False,
        revises_thought: Optional[int] = None,
        branch_from_thought: Optional[int] = None,
        branch_id: Optional[str] = None,
        needs_more_thoughts: bool = False
    ):
        self.thought = thought
        self.thought_number = thought_number
        self.total_thoughts = total_thoughts
        self.next_thought_needed = next_thought_needed
        self.is_revision = is_revision
        self.revises_thought = revises_thought
        self.branch_from_thought = branch_from_thought
        self.branch_id = branch_id
        self.needs_more_thoughts = needs_more_thoughts


class SequentialThinkingServer:
    """Sequential Thinking サーバー"""
    
    def __init__(self):
        self.thought_history: List[ThoughtData] = []
        self.branches: Dict[str, List[ThoughtData]] = {}
    
    def format_thought(self, thought_data: ThoughtData) -> str:
        """思考をフォーマット"""
        prefix = ""
        context = ""
        
        if thought_data.is_revision:
            prefix = "🔄 Revision"
            context = f" (revising thought {thought_data.revises_thought})"
        elif thought_data.branch_from_thought:
            prefix = "🌿 Branch"
            context = f" (from thought {thought_data.branch_from_thought}, ID: {thought_data.branch_id})"
        else:
            prefix = "💭 Thought"
            context = ""
        
        header = f"{prefix} {thought_data.thought_number}/{thought_data.total_thoughts}{context}"
        border_length = max(len(header), len(thought_data.thought)) + 4
        border = "─" * border_length
        
        return f"""
┌{border}┐
│ {header} │
├{border}┤
│ {thought_data.thought.ljust(border_length - 2)} │
└{border}┘"""
    
    def process_thought(
        self,
        thought: str,
        thought_number: int,
        total_thoughts: int,
        next_thought_needed: bool,
        is_revision: bool = False,
        revises_thought: Optional[int] = None,
        branch_from_thought: Optional[int] = None,
        branch_id: Optional[str] = None,
        needs_more_thoughts: bool = False
    ) -> str:
        """思考を処理"""
        
        # 思考番号が総数を超えた場合、総数を調整
        if thought_number > total_thoughts:
            total_thoughts = thought_number
        
        thought_data = ThoughtData(
            thought=thought,
            thought_number=thought_number,
            total_thoughts=total_thoughts,
            next_thought_needed=next_thought_needed,
            is_revision=is_revision,
            revises_thought=revises_thought,
            branch_from_thought=branch_from_thought,
            branch_id=branch_id,
            needs_more_thoughts=needs_more_thoughts
        )
        
        # 履歴に追加
        self.thought_history.append(thought_data)
        
        # ブランチの場合、ブランチ履歴に追加
        if branch_from_thought and branch_id:
            if branch_id not in self.branches:
                self.branches[branch_id] = []
            self.branches[branch_id].append(thought_data)
        
        # フォーマットされた思考を返す
        formatted = self.format_thought(thought_data)
        
        # 結果をJSON形式で返す
        result = {
            "thoughtNumber": thought_number,
            "totalThoughts": total_thoughts,
            "nextThoughtNeeded": next_thought_needed,
            "branches": list(self.branches.keys()),
            "thoughtHistoryLength": len(self.thought_history),
            "formatted": formatted
        }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
