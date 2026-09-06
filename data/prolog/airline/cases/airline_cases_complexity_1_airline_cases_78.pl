/* ----------  RULES FROM THE STATUTE (only what is needed for this case)  -------- */
% base checked-bag fee (Basic-Economy, within U.S.)
base_fee(1,40).
base_fee(2,45).
base_fee(3,150).
base_fee(N,200) :- N>=4.

% oversize fee (within U.S.)
oversize_fee(Sum,0)   :- Sum =< 62.
oversize_fee(Sum,30)  :- Sum > 62 , Sum =< 65.
oversize_fee(Sum,200) :- Sum > 65 , Sum =< 115.

% overweight fee (within U.S.)
overweight_fee(W,0)    :- W =< 50.
overweight_fee(W,30)   :- W > 50 , W =< 53.
overweight_fee(W,100)  :- W > 53 , W =< 70.
overweight_fee(W,200)  :- W > 70 , W =< 100.

% extra fee for a bag is the higher of its oversize / overweight surcharges
extra_fee(Id,Extra) :-
    item(Id,L,W,H,Weight),
    Sum is L+W+H,
    oversize_fee(Sum,OS),
    overweight_fee(Weight,OW),
    Extra is max(OS,OW).

% A carry-on must not exceed 22*14*9 in.
carry_on(Id) :-
    item(Id,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

% a checked bag is any bag that is not the single free carry-on
checked_bag(Id) :-
    item(Id,_,_,_,_),
    \+ carry_on(Id).

/* -------------------------------  CASE FACTS  ---------------------------------- */
ticket_cost(122).

item(bag1,22,14,7,9).      % backpack - free carry-on
item(bag2,38,14,12,79).
item(bag3,38,14,12,87).
item(bag4,37,21,11,53).
item(bag5,45,31,19,51).
item(bag6,38,21,12,74).
item(bag7,34,20,9,93).
item(bag8,37,13,13,65).

/* -------------------  CALCULATE COST OF CHECKED BAGS  ------------------------- */
bag_cost(Id,Index,Cost) :-
    base_fee(Index,Base),
    extra_fee(Id,Extra),
    Cost is Base + Extra.

checked_bags_ids(IDs) :-
    findall(Id,checked_bag(Id),IDs).

checked_bags_total_cost(Total) :-
    checked_bags_ids(IDs),
    checked_bags_total_cost(IDs,1,Total).

checked_bags_total_cost([],_,0).
checked_bags_total_cost([Id|Rest],Index,Total) :-
    bag_cost(Id,Index,Cost1),
    NextIndex is Index+1,
    checked_bags_total_cost(Rest,NextIndex,CostRest),
    Total is Cost1 + CostRest.

/* ---------------------------  OVERALL TOTAL  ----------------------------------- */
total_cost(Total) :-
    checked_bags_total_cost(BagsCost),
    ticket_cost(Ticket),
    Total is Ticket + BagsCost.

/* ----------------------------  QUERY & OUTPUT  -------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.