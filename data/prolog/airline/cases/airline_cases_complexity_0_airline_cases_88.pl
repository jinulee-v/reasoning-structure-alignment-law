/* -------------  Statutory rules that apply to this case ------------- */

/* Basic-Economy checked-bag base fees for the region
   "within / between the U.S. and Canada"                       */
checked_bag_base_fee(basic_economy, us_canada, 1, 35).
checked_bag_base_fee(basic_economy, us_canada, 2, 45).
checked_bag_base_fee(basic_economy, us_canada, 3, 150).
checked_bag_base_fee(basic_economy, us_canada, N, 200) :- N >= 4.

/* Oversize fees (length+width+height in inches) */
oversize_fee(Sum, 0)   :- Sum =< 62.
oversize_fee(Sum, 30)  :- Sum  > 62, Sum =< 65.
oversize_fee(Sum, 200) :- Sum  > 65, Sum =< 115.

/* Over-weight fees (pounds) */
overweight_fee(W, 0)    :- W =< 50.
overweight_fee(W, 30)   :- W  > 50, W =< 53.
overweight_fee(W, 100)  :- W  > 53, W =< 70.
overweight_fee(W, 200)  :- W  > 70, W =< 100.

/* Extra fee on a bag is the higher of its oversize / overweight fee */
extra_fee(L, W, H, P, Extra) :-
        Sum is L+W+H,
        oversize_fee(Sum, OS),
        overweight_fee(P, OW),
        Extra is max(OS, OW).

/* Carry-on test: every dimension within 22*14*9 inches            */
is_carry_on(L, W, H) :- L =< 22, W =< 14, H =< 9.

/* ---------------- Facts for Mary's itinerary ---------------- */

ticket_price(169).
passenger_class(basic_economy).
route(toronto, new_orleans, us_canada).

/* bag(Order, Id, Length, Width, Height, Weight)                   */
bag(1, small_backpack,     20, 12,  7,  9).
bag(2, large_backpack,     43, 17, 18, 52).
bag(3, luggage_box_1,      44, 21, 19, 53).
bag(4, luggage_box_2,      53, 29, 26, 53).
bag(5, heavy_backpack,     33, 21, 10, 85).

/* ---------------- Deriving which bags are checked --------------- */

/* checked_bag(Index, Id, L, W, H, P)
   Index = 1 for Mary's 1st checked bag, 2 for her 2nd, ...          */
checked_bag(Idx, Id, L, W, H, P) :-
        bag(Ord, Id, L, W, H, P),
        \+ is_carry_on(L, W, H),            % not free carry-on
        findall(Prev,
                (bag(O2, _, L2, W2, H2, _), O2 < Ord,
                 \+ is_carry_on(L2, W2, H2)),
                PrevList),
        length(PrevList, NPrev),
        Idx is NPrev + 1.

/* Fee for one checked bag */
checked_bag_total_fee(Idx, L, W, H, P, Fee) :-
        passenger_class(Class),
        route(_, _, Region),
        checked_bag_base_fee(Class, Region, Idx, Base),
        extra_fee(L, W, H, P, Extra),
        Fee is Base + Extra.

/* ---------------- Summing everything ---------------- */

total_bag_fees(Total) :-
        findall(F,
               (checked_bag(Idx, _, L, W, H, P),
                checked_bag_total_fee(Idx, L, W, H, P, F)),
               Fs),
        sumlist(Fs, Total).

total_cost(Total) :-
        ticket_price(Tix),
        total_bag_fees(Bags),
        Total is Tix + Bags.

/* --------------------  Query & print  --------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.