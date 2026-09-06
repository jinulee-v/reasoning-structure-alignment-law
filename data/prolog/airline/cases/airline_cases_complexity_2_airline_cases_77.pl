/*****************************************************************
  Statutory rules (only the parts that are needed for this case)
*****************************************************************/

% ----  Carry-on allowance --------------------------------------
carry_on_size(22,14,9).            % L,W,H in inches

% ----  Checked-bag base fees  (Main-Cabin, S. Korea -> U.S.) ---
% Order = position among the checked bags after the free carry-on
base_checked_fee(1,0).
base_checked_fee(2,100).
base_checked_fee(N,200) :- N>=3.

% ----  Overweight fees  (to / from South Korea) ----------------
overweight_fee(W,450) :- W > 70,  W =< 100.
overweight_fee(W,100) :- W > 53, W =< 70.
overweight_fee(W,30)  :- W > 50, W =< 53.
overweight_fee(W,0)   :- W =< 50.

% ----  Oversize fees (to / from South Korea) -------------------
oversize_fee(D,200) :- D > 65,  D =< 115.
oversize_fee(D,30)  :- D > 62,  D =< 65.
oversize_fee(D,0)   :- D =< 62.

% ----  Auxiliary predicates ------------------------------------
dimension_sum(L,W,H,Sum) :- Sum is L+W+H.

max(A,B,A) :- A>=B.
max(A,B,B) :- B>A.

/*****************************************************************
  Facts describing Thomas' journey
*****************************************************************/

ticket_price(518).          % Flight ticket itself in USD
passenger_class(main_cabin).
route(incheon, chicago).    % South Korea  -> U.S. (trans-pacific)

% Bag facts: bag(Id, Length, Width, Height, Weight).
bag(2,35,15,14,84).
bag(3,51,32,31,64).
bag(4,38,13,13,77).
bag(5,48,25,24,93).
bag(6,34,17,14,60).
bag(7,36,13,14,53).
bag(8,37,19,9, 68).
bag(9,33,21,9, 63).
bag(10,52,33,25,68).
bag(11,41,29,16,62).

/*****************************************************************
  Rules that compute every bag's cost
*****************************************************************/

% order(Id, Order) - fixed order in which Thomas checks the bags
order(2,1).  order(3,2).  order(4,3).  order(5,4).  order(6,5).
order(7,6).  order(8,7).  order(9,8).  order(10,9). order(11,10).

% extra_fee(Weight, DimSum, Fee) - highest of overweight / oversize
extra_fee(W,D,F) :-
    overweight_fee(W,WF),
    oversize_fee(D,SF),
    max(WF,SF,F).

% bag_cost(Id,Cost) - total cost (base + extra) for a checked bag
bag_cost(Id,Cost) :-
    bag(Id,L,W,H,Weight),
    dimension_sum(L,W,H,DimSum),
    order(Id,Order),
    base_checked_fee(Order,BaseFee),
    extra_fee(Weight,DimSum,Extra),
    Cost is BaseFee + Extra.

/*****************************************************************
  Summations
*****************************************************************/

sum_list([],0).
sum_list([H|T],S) :- sum_list(T,R), S is H+R.

total_checked_bag_fees(Total) :-
    findall(Cost, bag_cost(_,Cost), Costs),
    sum_list(Costs,Total).

total_cost(Total) :-
    ticket_price(Ticket),
    total_checked_bag_fees(Bags),
    % (no special-needs charges in this case)
    Total is Ticket + Bags.

/*****************************************************************
  Query: print the answer and halt
*****************************************************************/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.