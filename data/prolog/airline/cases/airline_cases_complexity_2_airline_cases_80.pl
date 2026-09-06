/************************************************************************
  Statutory rules (only those needed for this case)
************************************************************************/

% free checked-bag allowance for Premium Economy on American Airlines
free_checked_bags(premium_economy, 2).

% checked-bag base fees (within / between U.S., Puerto Rico, U.S.V.I., Canada)
base_bag_fee(BagIndex, Fee) :-
    BagIndex =< 2  -> Fee = 0              % 1st - 2nd bag
 ;  BagIndex =:= 3 -> Fee = 150            % 3rd bag
 ;  BagIndex  > 3 -> Fee = 200.            % 4th bag +

/*  Over-weight surcharges - within U.S.
    ------------------------------------------------------------------
    W = bag weight in pounds, S = surcharge in U.S. dollars            */
overweight_surcharge(W, 0  ) :- W =< 50,  !.
overweight_surcharge(W, 30 ) :- W  > 50, W =< 53, !.
overweight_surcharge(W, 100) :- W  > 53, W =< 70, !.
overweight_surcharge(W, 200) :- W  > 70, W =< 100.

 /* Over-size surcharges - within U.S.
    ------------------------------------------------------------------
    D = L+W+H (inches), S = surcharge                                    */
oversize_surcharge(D, 0  ) :- D =< 62, !.
oversize_surcharge(D, 30 ) :- D  > 62, D =< 65, !.
oversize_surcharge(D, 200) :- D  > 65, D =< 115.

/*  The statute says that when a bag is both over-weight and over-size
    "the higher fee between oversize and overweight applies".           */
bag_surcharge(W, D, S) :-
    overweight_surcharge(W, OW),
    oversize_surcharge(D,   OS),
    S is max(OW, OS).

/************************************************************************
  Facts describing Robert's trip
************************************************************************/

% flight facts ---------------------------------------------------------
class(premium_economy).
itinerary(domestic).                % Houston (TX) - Salt Lake City (UT)
ticket_price(32).

% baggage facts  (bag(Id, L, W, H, Weight) - all dimensions in inches) -
bag( 1, 19, 12,  8, 11).   % carry-on (free)
bag( 2, 35, 16, 14, 70).
bag( 3, 33, 22, 10, 88).
bag( 4, 49, 29, 21, 58).
bag( 5, 46, 28, 25, 56).
bag( 6, 48, 35, 24, 69).
bag( 7, 37, 14, 13, 90).
bag( 8, 38, 12, 13, 51).
bag( 9, 37, 18,  9, 52).
bag(10, 36, 18, 10, 85).
bag(11, 47, 33, 24, 51).

/************************************************************************
  Derivations
************************************************************************/

% checked_bag/5 : every bag except the permitted 1 carry-on (bag 1)
checked_bag(Id, L, W, H, WT) :-
    bag(Id, L, W, H, WT),
    Id \= 1.

% number of checked bags
checked_bag_count(N) :-
    findall(Id, checked_bag(Id,_,_,_,_), L),
    length(L, N).

% surcharge for one checked bag
checked_bag_surcharge(Id, S) :-
    checked_bag(Id, L, W, H, WT),
    D is L + W + H,
    bag_surcharge(WT, D, S).

% sum of all surcharges
surcharge_total(Total) :-
    findall(S, checked_bag_surcharge(_, S), L),
    sum_list(L, Total).

% total base bag fees (order independent for this domestic journey)
bag_fees_total(FeeTotal) :-
    checked_bag_count(N),
    ( N =< 2 -> FeeTotal = 0
    ; N  =:= 3 -> FeeTotal = 150
    ; N  >  3 -> FeeTotal is 150 + 200*(N-3)
    ).

% overall total
total_cost(Total) :-
    ticket_price(Ticket),
    bag_fees_total(BagFees),
    surcharge_total(Surcharges),
    Total is Ticket + BagFees + Surcharges.

/************************************************************************
  Query - print the answer and halt
************************************************************************/
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.