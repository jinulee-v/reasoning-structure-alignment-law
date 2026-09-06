/******************************************************************
*  Statutory rules (only the parts that matter for this case)
******************************************************************/

/* flight facts: passenger, origin, destination, class, fare */
flight(jennifer, ottawa, boston, basic_economy, 323).

/* every piece of luggage: id, length, width, height, weight (lbs) */
bag(1,20,13, 6, 11).   /* carry-on                                        */
bag(2,35,16,12, 57).
bag(3,52,37,26, 63).
bag(4,39,27,15, 52).
bag(5,42,20,19, 51).
bag(6,38,25,17, 52).
bag(7,51,26,25, 62).
bag(8,34,17,14, 53).
bag(9,39,16,12, 52).
bag(10,35,14,14, 76).
bag(11,50,29,28, 58).

/********************  Carry-on qualification  ********************/
% personal-item rules are irrelevant - passenger has none
carry_on(ID) :-
    bag(ID,L,W,H,_),
    L =< 22, W =< 14, H =<  9.

/********************  Checked bags list and order  ***************/
checked_bag(ID) :- bag(ID,_,_,_,_), \+ carry_on(ID).

/* position of a checked bag (1st, 2nd, 3rd ...) when sorted by ID   */
bag_index(ID,N) :-
    findall(B,checked_bag(B),Bs0),
    sort(Bs0,Bs),                % deterministic ordering
    nth1(N,Bs,ID).

/********************  BASE checked-bag fees (US <-> Canada) ******/
base_fee(Order,35)  :- Order =:= 1.      % 1st bag
base_fee(Order,45)  :- Order =:= 2.      % 2nd bag
base_fee(Order,150) :- Order =:= 3.      % 3rd bag
base_fee(Order,200) :- Order  >= 4.      % 4th bag and higher

/********************  Over-WEIGHT surcharges  ********************/
overweight_fee(W,0)   :- W =< 50.
overweight_fee(W,30)  :- W > 50,  W =< 53.
overweight_fee(W,100) :- W > 53,  W =< 70.
overweight_fee(W,200) :- W > 70,  W =< 100.

/********************  Over-SIZE surcharges (US / Canada route) ***/
oversize_fee(S,0)    :- S =< 62.
oversize_fee(S,30)   :- S > 62, S =< 65.
oversize_fee(S,200)  :- S > 65, S =< 115.

/********************  One-bag surcharge (higher of the two) *****/
surcharge(Weight,SizeSum,Fee) :-
    overweight_fee(Weight,OW),
    oversize_fee(SizeSum,OS),
    Fee is max(OW,OS).

/********************  Total fee for one checked bag **************/
bag_fee(Fee) :-
    checked_bag(ID),
    bag_index(ID,Order),
    base_fee(Order,Base),
    bag(ID,L,W,H,Weight),
    SizeSum is L+W+H,
    surcharge(Weight,SizeSum,Surch),
    Fee is Base + Surch.

/********************  Grand total for the passenger **************/
total_cost(Total) :-
    flight(jennifer,_,_,_,Ticket),
    findall(F,bag_fee(F),BagFees),
    sum_list(BagFees,BagsTotal),
    Total is Ticket + BagsTotal.

/********************  Produce the answer *************************/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.