/* ---------- Rules that encode the statutes (only what is relevant to the case) ---------- */

/* price of the ticket itself */
ticket_price(53).

/* ------------------  Passenger's bags (facts from the case) ------------------ */
/* bag(ID, Length, Width, Height, Weight). */
bag(1,22,14, 9, 10).   /* fits the free carry-on limits              */
bag(2,33,21, 9, 57).
bag(3,36,18,16, 82).
bag(4,35,16,14, 53).
bag(5,48,29,22, 99).
bag(6,34,20, 9, 72).
bag(7,40,24,14, 51).
bag(8,41,24,18, 64).
bag(9,37,25,12, 63).
bag(10,40,21,16, 81).
bag(11,38,17, 9, 83).

/* ------------------  Free carry-on rule  ------------------ */
carry_on(BagID) :-
    bag(BagID,L,W,H,_),
    L =< 22, W =< 14, H =< 9.        /* within the carry-on dimensions */

/* ------------------  Checked bags list ------------------ */
checked_bag_ids(Checked) :-
    findall(Id, (bag(Id,_,_,_,_), \+ carry_on(Id)), Checked).

/* ------------------  Base checked-bag fee (within U.S., Main Cabin) ------------------ */
base_fee(1,40).
base_fee(2,45).
base_fee(3,150).
base_fee(N,200) :- N>=4.

/* ------------------  Oversize fees (within U.S.) ------------------ */
oversize_fee(Size,0)   :- Size =< 62.
oversize_fee(Size,30)  :- Size > 62, Size =< 65.
oversize_fee(Size,200) :- Size > 65, Size =< 115.

/* ------------------  Overweight fees (within U.S.) ------------------ */
overweight_fee(W,0)   :- W =< 50.
overweight_fee(W,30)  :- W  > 50, W =< 53.
overweight_fee(W,100) :- W  > 53, W =< 70.
overweight_fee(W,200) :- W  > 70, W =< 100.

/* ------------------  Extra fee for a single bag ------------------ */
/* If both oversize and overweight apply, charge only the higher one. */
extra_fee(Size,Weight,Fee) :-
    oversize_fee(Size,OS), overweight_fee(Weight,OW),
    (OS >= OW -> Fee = OS ; Fee = OW).

/* ------------------  Cost for each checked bag ------------------ */
bag_cost(BagID,Index,Cost) :-
    bag(BagID,L,W,H,Weight),
    Size  is L+W+H,
    extra_fee(Size,Weight,Extra),
    base_fee(Index,Base),
    Cost is Base + Extra.

/* build list of costs in the order bags are checked (2,3,4,...) */
checked_bag_costs(Costs) :-
    checked_bag_ids(Ids),
    costs_from_ids(Ids,1,Costs).

costs_from_ids([],_,[]).
costs_from_ids([Id|Rest],Num,[Cost|More]) :-
    bag_cost(Id,Num,Cost),
    Next is Num+1,
    costs_from_ids(Rest,Next,More).

/* simple list sum */
sumlist([],0).
sumlist([H|T],Sum) :- sumlist(T,S0), Sum is S0+H.

/* ------------------  Total cost for the passenger ------------------ */
total_cost(Total) :-
    ticket_price(Ticket),
    checked_bag_costs(Costs),
    sumlist(Costs,BagsTotal),
    Total is Ticket + BagsTotal.

/* ------------------  Query & output ------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.