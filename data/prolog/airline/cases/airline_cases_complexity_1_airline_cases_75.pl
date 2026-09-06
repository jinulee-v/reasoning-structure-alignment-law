/********************************************************************
  Statutory rules (subset needed for this case only)
********************************************************************/

% ticket price for the itinerary (Miami - New Orleans)
ticket_cost(145).

% route - all bags are "within U.S."
within_us.

% Base checked-bag fee schedule for Basic-Economy passengers
% base_fee(BagNumber, Fee).
base_fee(1, 40).
base_fee(2, 45).
base_fee(3, 150).
base_fee(N, 200) :- N >= 4.          % bags 4,5,6,7 ...

/* ---------------- Oversize fees (within U.S.) ---------------- */

% oversize_fee(DimSum, Fee)
% 0-62 in  -> no oversize fee
% 62<Dim<=65 -> $30
% 65<Dim<=115 -> $200
oversize_fee(Dim, 0)   :- Dim =< 62.
oversize_fee(Dim, 30)  :- Dim  > 62, Dim =< 65.
oversize_fee(Dim, 200) :- Dim  > 65, Dim =< 115.

/* ---------------- Over-weight fees (within U.S.) -------------- */

% overweight_fee(WeightLbs, Fee)
overweight_fee(W, 0)   :- W =< 50.
overweight_fee(W, 30)  :- W  > 50, W =< 53.
overweight_fee(W, 100) :- W  > 53, W =< 70.
overweight_fee(W, 200) :- W  > 70, W =< 100.

/* When both oversize and overweight apply, charge the higher one */
extra_fee(Dim, W, Fee) :-
        oversize_fee(Dim, F1),
        overweight_fee(W,  F2),
        (F1 >= F2 -> Fee = F1 ; Fee = F2).

/********************************************************************
  Facts for Elizabeth's items
********************************************************************/

% item(ID, L, W, H, Weight).
item(1, 19, 14,  7,  6).    % backpack - will be carry-on
item(2, 38, 14, 13, 51).
item(3, 46, 33, 24, 80).
item(4, 33, 23,  9, 51).
item(5, 36, 14, 13, 53).
item(6, 38, 12, 14, 51).
item(7, 44, 23, 23, 81).
item(8, 44, 28, 22, 84).

/* ---------------  Derived facts  ---------------------------------*/

% carry_on(ItemID) - exactly one item may be carried on
carry_on(1).

% checked(ItemID, Ordinal) - gives the running order of checked bags
checked(ID, N) :-
        item(ID,_,_,_,_),
        \+ carry_on(ID),
        findall(I,(item(I,_,_,_,_),\+ carry_on(I)),L),
        nth1(N,L,ID).

% dimension_sum(ID, SumInches)
dimension_sum(ID, Sum) :-
        item(ID,L,W,H,_),
        Sum is L+W+H.

/********************************************************************
  Cost calculation
********************************************************************/

% cost_of_bag(ItemID, Cost)  (Cost = base fee + extra fee)
cost_of_bag(ID, Cost) :-
        checked(ID, Ord),
        base_fee(Ord, Base),
        dimension_sum(ID, Dim),
        item(ID,_,_,_,Wt),
        extra_fee(Dim, Wt, Extra),
        Cost is Base + Extra.

% total for all checked bags
total_checked_cost(Total) :-
        findall(C, (checked(ID,_), cost_of_bag(ID,C)), Cs),
        sum_list(Cs, Total).

% grand total (ticket + bags)
total_cost(Grand) :-
        ticket_cost(T),
        total_checked_cost(Bags),
        Grand is T + Bags.

/********************************************************************
  Query: print the total cost
********************************************************************/
:- total_cost(Total),
   format('Total cost: ~w~n', [Total]).
:- halt.