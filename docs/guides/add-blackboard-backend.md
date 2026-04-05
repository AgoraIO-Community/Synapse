# Add Blackboard Backend

New blackboard backends should implement the blackboard interfaces rather than bypassing them.

Recommended sequence:

1. implement repository/store interfaces
2. implement revision and subscription behavior
3. verify query semantics
4. verify claim/lease semantics

Keep behavior aligned with the protocol and architecture docs before optimizing for backend-specific storage patterns.
