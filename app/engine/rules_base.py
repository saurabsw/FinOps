from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class RuleEvaluationResult:
    is_waste: bool
    rule_id: str
    rule_name: str
    category: str
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW
    monthly_savings_estimate: float
    currency: str
    reason: str
    inspect_command: str
    remediation_command: str

class BaseRule(ABC):
    """Abstract interface for all built-in deterministic FinOps rules."""

    @property
    @abstractmethod
    def rule_id(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        pass

    @property
    @abstractmethod
    def severity(self) -> str:
        pass

    @abstractmethod
    def evaluate(self, resource: Dict[str, Any]) -> Optional[RuleEvaluationResult]:
        """
        Evaluates a canonical resource dictionary.
        Returns RuleEvaluationResult if waste is detected, else None.
        Ensures 0 false positives on active resources.
        """
        pass
