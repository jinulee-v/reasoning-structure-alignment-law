/* ---------  Statutory rules needed for this case  --------- */

:- use_module(library(lists)).

/*  Oversize fees on a route "to / from India ..." (Jennifer's route)  */
oversize_fee(Size, Fee) :-                    % Size is L+W+H in inches
    Size =< 62  ,          Fee = 0  , !.
oversize_fee(Size, Fee) :-
    Size  =< 65 ,          Fee = 30 , !.      % 62  < size =< 65
oversize_fee(Size, Fee) :-
    Size  =< 115,          Fee = 200, !.      % 65  < size =< 115

/*  Over-weight fees on a route "to / from India ..." (Premium Economy)  */
overweight_fee(W, Fee) :-                     % W is weight in lbs
    W =< 50 ,            Fee = 0  , !.
overweight_fee(W, Fee) :-
    W  =< 53 ,           Fee = 30 , !.        % 50 < W =< 53
overweight_fee(W, Fee) :-
    W  =< 70 ,           Fee = 100, !.        % 53 < W =< 70
overweight_fee(W, Fee) :-
    W  =< 100,           Fee = 450.           % 70 < W =< 100

/*  For a bag that is both oversize and overweight,
    the higher of the 2 surcharges applies              */
surcharge(Size, Weight, Charge) :-
    oversize_fee(Size, OF),
    overweight_fee(Weight, WF),
    ( OF >= WF -> Charge = OF ; Charge = WF ).

/*  Checked-bag base fees for a PREMIUM-ECONOMY customer
    flying to / from India                               */
base_fee(BagNumber, Fee) :-
    ( BagNumber = 1 ; BagNumber = 2 ) ->  Fee = 0 ;
    ( BagNumber = 3 ; BagNumber = 4 ) ->  Fee = 200.

/* ---------  Facts for Jennifer's trip  --------- */

/* The 4 checked bags (personal item is free and omitted)           */
/* bag(ID, Length, Width, Height, Weight).                          */
bag(b2, 43, 23, 18, 52).   % backpack
bag(b3, 33, 22, 10, 79).   % backpack
bag(b4, 38, 16, 11, 61).   % luggage box
bag(b5, 34, 19, 12, 52).   % backpack

/* Ticket price */
ticket_price(677).

/* ---------  Helper predicates  --------- */

bag_size(ID, S)  :- bag(ID,L,W,H,_), S is L+W+H.
bag_weight(ID,W) :- bag(ID,_,_,_,W).

bag_surcharge(ID, Charge) :-
    bag_size(ID,S),
    bag_weight(ID,W),
    surcharge(S, W, Charge).

/* Number the 4 checked bags in any fixed order.
   Here we keep the declaration order.                       */
bag_order([b2,b3,b4,b5]).

base_fees_total(BaseTotal) :-
    bag_order(Bs),
    findall(F,
            ( nth1(N,Bs,_), base_fee(N,F) ),
            Fs),
    sumlist(Fs, BaseTotal).

surcharges_total(SurchTot) :-
    findall(C,
            ( bag(ID,_,_,_,_), bag_surcharge(ID,C) ),
            Cs),
    sumlist(Cs, SurchTot).

total_cost(Total) :-
    ticket_price(Tix),
    base_fees_total(Base),
    surcharges_total(Surch),
    Total is Tix + Base + Surch.

/* ---------  Query --------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.