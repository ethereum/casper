#Design Document
##Initialize the following: 

`slashed_validators : [num]`
`slash_total : bool`

In `logout():`
	#check if the validator acted in a malicious manner before and if the total slash condition has been invoked: line 322
	`if slash_total && slashed_validators[validator_index]:
		delete_validator(validator_index)
	else: 
		proceed `

In delete_validator:
	slashed_validators[validator_index] = 0

In withdraw_validator: line 349
	if slash_total && slashed_validators[validator_index]:
		delete_validator(validator_index)
	else: 
		proceed 

In proc_reward:
	if slash_total && slashed_validators[validator_index]:
		delete_validator(validator_index)
	else: 
		proceed 
		
In vote: (line 390)
	if slash_total && slashed_validators[validator_index]:
		delete_validator(validator_index)
	else: 
		proceed 
In slash: 

    # Slash total condition invoked
    if self.total_destroyed >= (1/3) * get_total_curdyn_deposits():
        self.total_destroyed += 0.835 * validator_deposit
        self.delete_validator(validator_index_1)
	slash_total = true
else: 
	…. (same as v1.5 condition)
	slashed_validators[validator_index_1] = 1
	
