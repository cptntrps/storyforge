"""Check results. Every check returns Check rows; a script decides, the model never does."""

from dataclasses import dataclass, field, asdict

RESULTS = ('PASS', 'FAIL', 'NA', 'DISAGREE')
METHODS = ('script', 'judged')


@dataclass
class Check:
    id: str
    method: str
    result: str
    evidence: list = field(default_factory=list)

    def __post_init__(self):
        if self.result not in RESULTS:
            raise ValueError(f'{self.id}: result {self.result!r} not in {RESULTS}')
        if self.method not in METHODS:
            raise ValueError(f'{self.id}: method {self.method!r} not in {METHODS}')

    def to_dict(self):
        return asdict(self)


def verdict(check_id, failures, method='script', fail_result='FAIL'):
    """One Check from a list of failure evidence rows: empty list is PASS."""
    return Check(check_id, method, 'PASS' if not failures else fail_result, list(failures))
