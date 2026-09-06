/* ---------- Statutory rules relevant to this case ---------- */

/* Main-Plus customers: first 2 checked bags have no checked-bag fee,
   bags 3+ cost $200 each on U.S. <-> China itineraries                */
bag_fee(Index, Fee) :-
    Index =< 2  -> Fee = 0
 ;                      Fee = 200.

/* Over-WEIGHT fees - U.S. <-> China (all cabins) */
overweight_fee(Weight, Fee) :-
    Weight =< 50                       -> Fee = 0
 ;  Weight =< 53                       -> Fee = 30
 ;  Weight =< 70                       -> Fee = 100
 ;  Weight =< 100                      -> Fee = 450
 ;                                      fail.   /* >100 lb not accepted */

/* Over-SIZE fees - U.S. <-> China */
oversize_fee(SizeSum, Fee) :-
    SizeSum =< 62                      -> Fee = 0
 ;  SizeSum =< 65                      -> Fee = 30
 ;  SizeSum =< 115                     -> Fee = 200
 ;                                      fail.   /* >115 in not accepted */

/* For a given bag, the higher of over-size / over-weight applies
   (plus any checked-bag fee)                                            */
bag_cost(Index, Weight, SizeSum, Cost) :-
    bag_fee(Index, BagFee),
    overweight_fee(Weight, OW),
    oversize_fee(SizeSum,  OS),
    ( OW >= OS -> Surcharge = OW ; Surcharge = OS ),
    Cost is BagFee + Surcharge.

/* ---------- Facts: Robert's checked items ---------- */
/* bag(Index, Weight(lbs), SizeSum(in)) */

bag( 1, 82,  89).
bag( 2, 95, 113).
bag( 3, 60,  82).
bag( 4, 53,  65).
bag( 5, 88, 109).
bag( 6, 58,  73).
bag( 7, 51,  80).
bag( 8, 66,  78).
bag( 9, 93,  64).
bag(10, 96,  74).

/* ---------- Helper: sum of list ---------- */
sum_list([],0).
sum_list([H|T],S) :- sum_list(T,S1), S is H+S1.

/* ---------- Total for all checked bags ---------- */
total_bags_cost(Total) :-
    findall(C,
            ( bag(I,W,Sz), bag_cost(I,W,Sz,C) ),
            Cs),
    sum_list(Cs, Total).

/* ---------- Grand total (ticket + bags) ---------- */
ticket_price(1492).

total_cost(Total) :-
    ticket_price(Ticket),
    total_bags_cost(Bags),
    Total is Ticket + Bags.

/* ---------- Query & print result ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.