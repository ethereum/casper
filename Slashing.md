# Design Document

## Questions:
1)
In line 448 we do : `self.total_destroyed += validator_deposit * 24 / 25`
line 336: *What happened to the bounty i.e 1/25th the deposit? (Are we assuming its not deposited again?)*
In line 367:     

	if ((start_dynasty <= current_dynasty) and (current_dynasty < end_dynasty)):
       		self.total_curdyn_deposits += reward
  	if ((start_dynasty <= past_dynasty) and (past_dynasty < end_dynasty)):
        	self.total_prevdyn_deposits += reward

2)
*If that is the case why is reward getting added to the `self.total_curdyn_deposits` ?*

3)
In `deposit():`
*Can a validator not add more deposit to itself?*

4)
In `proc_reward():`
Why do we do the following? 
    
    if current_dynasty == end_dynasty - 1:
        self.next_dynasty_wei_delta -= reward


## Design:
### Initialize the following: 
	
`slashed_validators : [num]`

`slash_total : bool `	

### Add the following
In `logout(): `

	#check if the validator acted in a malicious manner before and if the total slash condition has been invoked: line 322
	if slash_total && slashed_validators[validator_index]:
		delete_validator(validator_index)
	else:
		proceed 

In `delete_validator:`

	slashed_validators[validator_index] = 0

In `withdraw_validator:` line 349

	if slash_total && slashed_validators[validator_index]:
		delete_validator(validator_index)
	else: 
		proceed 

In `proc_reward:`

	if slash_total && slashed_validators[validator_index]:
		delete_validator(validator_index)
	else: 
		proceed 
		
In `vote:` (line 390)

	if slash_total && slashed_validators[validator_index]:
		delete_validator(validator_index)
	else: 
		proceed 
		
In `slash:` 

	if self.total_destroyed >= (1/3) * get_total_curdyn_deposits():
       		self.total_destroyed += 0.835 * validator_deposit
       		self.delete_validator(validator_index_1)
      		slash_total = true
   	else: 
		(same as v1.5 condition)
		slashed_validators[validator_index_1] = 1


	
