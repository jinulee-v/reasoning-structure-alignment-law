/* ---------------  Facts for Joseph's trip --------------- */

% ticket price
ticket_price(476).

% passenger class and itinerary (only what's needed for pricing)
class(business).
route(europe_to_us).   % Rome (EU) -> Salt Lake City (US)

% bag(Number, Length, Width, Height, Weight).
bag(1, 18, 14,  6, 11).
bag(2, 33, 21, 11, 52).
bag(3, 44, 24, 19, 69).
bag(4, 45, 29, 18, 53).
bag(5, 37, 17,  9, 51).
bag(6, 34, 17, 13, 53).
bag(7, 46, 23, 20, 66).
bag(8, 38, 15, 12, 53).
bag(9, 37, 15, 11, 51).
bag(10,35, 19, 14, 57).
bag(11,41, 26, 18, 55).

/* ---------------  Utility predicates --------------- */

dims_sum(L,W,H,S) :- S is L+W+H.

/* ---------------  Identify personal item / carry-on / checked --------------- */

personal_item(N) :-
    bag(N,L,W,H,_),
    L =< 18, W =< 14, H =< 8.

carry_on(N) :-
    bag(N,L,W,H,_),
    L =< 22, W =< 14, H =< 9,
    \+ personal_item(N).

checked_bag(N) :-
    bag(N,_,_,_,_),
    \+ personal_item(N),
    \+ carry_on(N).

/* ---------------  Order of checked bags --------------- */

checked_bag_index(N,Idx) :-
    checked_bag(N),
    findall(B,(checked_bag(B),B<N),Bs),
    length(Bs,Len),
    Idx is Len+1.

/* ---------------  Base checked-bag fee (Business, Europe<->US) --------------- */

base_bag_fee(Index,Fee) :-
    ( Index =< 2 -> Fee = 0          % 1st & 2nd bags free
    ;              Fee = 200).       % 3rd+ bags $200 each

/* ---------------  Oversize fee (Europe<->US) --------------- */

oversize_fee(N,Fee) :-
    bag(N,L,W,H,_),
    dims_sum(L,W,H,S),
    ( S =< 62            -> Fee = 0
    ; S =< 65            -> Fee = 30
    ; S =< 115           -> Fee = 150
    ;                      Fee = 0 ).   % larger not needed in this case

/* ---------------  Overweight fee (universal amounts used here) --------------- */

overweight_fee(N,Fee) :-
    bag(N,_,_,_,Wt),
    ( Wt =< 50           -> Fee = 0
    ; Wt =< 53           -> Fee = 30
    ; Wt =< 70           -> Fee = 100
    ;                      Fee = 0 ).   % >70 not present

/* ---------------  Miscellaneous fee for a bag --------------- */

misc_fee(N,Fee) :-
    oversize_fee(N,O),
    overweight_fee(N,W),
    max_list([O,W],Fee).

/* ---------------  Charge for a checked bag --------------- */

bag_charge(N,Charge) :-
    checked_bag_index(N,Idx),
    base_bag_fee(Idx,Base),
    misc_fee(N,Misc),
    Charge is Base + Misc.

/* ---------------  Total baggage fees --------------- */

total_baggage_fees(Total) :-
    findall(C,(checked_bag(N),bag_charge(N,C)),Cs),
    sumlist(Cs,Total).

/* ---------------  Overall total cost --------------- */

total_cost(Total) :-
    ticket_price(Ticket),
    total_baggage_fees(BagFees),
    Total is Ticket + BagFees.

/* ---------------  Output --------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.