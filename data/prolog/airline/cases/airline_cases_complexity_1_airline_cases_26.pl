/*-------------------------------------------------
   Facts that describe the flight and the passenger
--------------------------------------------------*/

% ticket price
ticket_price(363).

% passenger class
passenger_class(main_plus).

% itinerary - only one origin / destination is needed for this case
origin(vancouver).
destination(atlanta).

% bags carried by the passenger
% bag(ID, Length, Width, Height, Weight).
bag(1, 18,12, 8,  8).      % small back-pack  -> personal item
bag(2, 54,32,27, 95).      % checked
bag(3, 50,25,24, 55).      % checked
bag(4, 34,17,13, 59).      % checked
bag(5, 33,22, 9, 55).      % checked
bag(6, 35,15,14, 52).      % checked
bag(7, 33,20,12, 52).      % checked
bag(8, 36,17,14, 62).      % checked


/*-------------------------------------------------
   Helpers
--------------------------------------------------*/

% sum of the 3 dimensions of a bag
size(ID, S) :-
    bag(ID, L,W,H,_),
    S is L+W+H.

% route category relevant for this case
route(us_canada).           % Vancouver - Atlanta

% max(A,B,Max)
max(A,B,A) :- A>=B.
max(A,B,B) :- B>A.


/*-------------------------------------------------
   Carry-on / personal item rules
--------------------------------------------------*/

% bag 1 is the only personal item, all others (ID>1) are checked
personal_item(ID) :- ID =:= 1.
checked_bag(ID)   :- bag(ID,_,_,_,_), \+ personal_item(ID).


/*-------------------------------------------------
   Main-Plus base checked-bag fees (Vancouver <-> Atlanta)
--------------------------------------------------*/

% order of a checked bag (1st, 2nd, 3rd ...) after
% removing the personal item from the sequence ID ascending
checked_bags_ordered(OrderedIDs) :-
    findall(ID, checked_bag(ID), IDs),
    sort(IDs, OrderedIDs).

bag_order(ID, N) :-
    checked_bags_ordered(List),
    nth1(N, List, ID).

% base fee that depends only on the bag order
base_fee(1, 0).           % Main-Plus gives the 1st bag free (extra allowance)
base_fee(2, 45).
base_fee(3, 150).
base_fee(N, 200) :- N>=4.


/*-------------------------------------------------
   Overweight fees  (route us_canada)
--------------------------------------------------*/
overweight_fee(W, 0)   :- W =< 50.
overweight_fee(W, 30)  :- W > 50,  W =< 53.
overweight_fee(W, 100) :- W > 53, W =< 70.
overweight_fee(W, 200) :- W > 70, W =< 100.

/*-------------------------------------------------
   Oversize fees  (route us_canada)
--------------------------------------------------*/
oversize_fee(S, 0)   :- S =< 62.
oversize_fee(S, 30)  :- S > 62, S =< 65.
oversize_fee(S, 200) :- S > 65, S =< 115.

/*-------------------------------------------------
   Extra fee for a bag = max(oversize, overweight)
--------------------------------------------------*/
extra_fee(ID, Fee) :-
    bag(ID,_,_,_,W),
    size(ID,S),
    overweight_fee(W, OW),
    oversize_fee(S,   OS),
    max(OW,OS, Fee).

/*-------------------------------------------------
   Total fee for each checked bag = base + extra
--------------------------------------------------*/
bag_fee(ID, Total) :-
    bag_order(ID, N),
    base_fee(N, Base),
    extra_fee(ID, Extra),
    Total is Base + Extra.

/*-------------------------------------------------
   Sum up all checked-bag fees
--------------------------------------------------*/
total_checked_bag_fees(Sum) :-
    findall(F, (checked_bag(ID), bag_fee(ID,F)), List),
    sum_list(List, Sum).

/*-------------------------------------------------
   Grand total = ticket + all bag fees
--------------------------------------------------*/
total_cost(Total) :-
    ticket_price(Ticket),
    total_checked_bag_fees(BagFees),
    Total is Ticket + BagFees.

/*-------------------------------------------------
   Produce the answer requested
--------------------------------------------------*/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.