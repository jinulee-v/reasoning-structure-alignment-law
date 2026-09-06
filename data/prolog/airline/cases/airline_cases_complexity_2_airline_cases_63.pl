/* ------------  Statutory rules needed for this case  ------------ */

/*  Size (L+W+H) -> oversize fee for a U.S. -> Japan itinerary        */
oversize_fee(Size,0   ) :- Size =< 62.
oversize_fee(Size,30  ) :- Size > 62, Size =< 65.
oversize_fee(Size,200 ) :- Size > 65, Size =< 115.

/*  Weight -> overweight fee for a U.S. -> Japan itinerary            */
overweight_fee(W,0   )  :- W =< 50.
overweight_fee(W,30  )  :- W > 50,  W =< 53.
overweight_fee(W,100 )  :- W > 53,  W =< 70.
overweight_fee(W,450 )  :- W > 70,  W =< 100.

/*  For a checked bag the *surcharge* is the HIGHER of the two fees  */
surcharge(Weight,Size,S) :- oversize_fee(Size,OS),
                            overweight_fee(Weight,OW),
                            ( OS >= OW -> S = OS ; S = OW ).

/*  Base checked-bag fees for Basic Economy U.S. <-> Japan             */
base_fee(1, 75).
base_fee(2,100).
base_fee(N,200) :- N >= 3.

/*  Total cost for a single checked bag with ordinal N               */
bag_cost(N,Weight,Size,Cost) :-
        base_fee(N,B),
        surcharge(Weight,Size,S),
        Cost is B + S.

/* ------------  Facts describing Emily's items  ------------------- */

/*  carry-on (free)  */
carryon(b1, 18,12,9,  6).

/*  checked bags : id, L,W,H,Weight  */
checked(1,b2, 38,13,14, 51).
checked(2,b3, 33,19,12, 61).
checked(3,b4, 35,16,14, 53).
checked(4,b5, 47,28,20, 52).
checked(5,b6, 33,18,12, 51).
checked(6,b7, 37,14,13, 51).
checked(7,b8, 50,31,25, 53).
checked(8,b9, 39,26,14, 84).
checked(9,b10,54,35,26, 81).
checked(10,b11,34,17,13, 63).

/* ------------  Aggregate cost computation  ----------------------- */

total_checked_cost(Total) :-
        findall(C,
               (checked(N,_,L,W,H,Weight),
                Size is L+W+H,
                bag_cost(N,Weight,Size,C)),
               Cs),
        sum_list(Cs,Total).

flight_ticket_cost(354).

total_cost(Total) :-
        total_checked_cost(Checked),
        flight_ticket_cost(Ticket),
        Total is Checked + Ticket.

/* ------------  Produce the answer  ------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.