/* -------- Statutory rules that apply to this itinerary ------------------- */

/*  Carry-on test (U.S.-Europe rules are the same as system-wide rules)      */
carry_on_size(L,W,H) :- L =< 22, W =< 14, H =< 9.

/*  Linear size of a piece of luggage                                        */
linear(L, W, H, S) :- S is L+W+H.

/* -------- Oversize charges (Europe <-> U.S.) --------------------------------
   -  >62 - 65 in  : $30
   -  >65 - 115 in : $150                                                     */
oversize_fee(S, 0   ) :- S =< 62.
oversize_fee(S, 30  ) :- S  > 62, S =< 65.
oversize_fee(S, 150 ) :- S  > 65, S =< 115.

/* -------- Over-weight charges (all cabins, Europe <-> U.S.) -----------------
   -  >50 - 53 lb  : $30
   -  >53 - 70 lb  : $100                                                     */
overweight_fee(W, 0   ) :- W =< 50.
overweight_fee(W, 30  ) :- W  > 50, W =< 53.
overweight_fee(W, 100 ) :- W  > 53, W =< 70.

/*  For a bag that is BOTH oversize and overweight, only the HIGHER of the
    2 surcharges is collected.                                               */
surcharge(W, S, F) :-
        oversize_fee(S, FO),
        overweight_fee(W, FW),
        (FO >= FW -> F = FO ; F = FW).

/* ---------------- Base checked-bag fees (Main Plus on Europe <-> U.S.) -------
   Main Plus = Main Cabin allowances + 1 extra free bag (max 2 free).
   1st & 2nd bag base fee ............... $0
   3rd bag and every bag after ... $200                                         */
base_fee(Index, 0   ) :- Index =< 2.     % two free checked bags
base_fee(Index, 200 ) :- Index  > 2.

/* ------------------------- Facts of the case ------------------------------ */

/*  Bag(id, Length, Width, Height, Weight).                                  */
bag(1,19,14, 8,  6).
bag(2,35,18,11, 68).
bag(3,41,27,21, 68).
bag(4,36,14,14, 64).
bag(5,37,14,12, 53).
bag(6,51,32,29, 51).
bag(7,33,18,14, 55).
bag(8,38,18, 9, 60).
bag(9,38,15,11, 53).
bag(10,39,19,11,53).
bag(11,42,28,22,51).

/*  Identify the single carry-on (the first piece that fits).                */
carry_on_id(ID) :-
        bag(ID,L,W,H,_), carry_on_size(L,W,H), !.  % first that matches

/*  A checked bag is any bag that is NOT the chosen carry-on.                */
checked_bag_id(ID) :-
        bag(ID,_,_,_,_), carry_on_id(C), ID \= C.

/*  Number every checked bag in ascending ID order to apply base-bag fees.   */
checked_bag_numbered(N,ID) :-
        findall(I, checked_bag_id(I), List),
        sort(List, Sorted),               % fixed ordering
        nth1(N,Sorted,ID).

/*  Cost for one checked bag (base fee + highest applicable surcharge)       */
checked_bag_cost(N, Cost) :-
        checked_bag_numbered(N,ID),
        bag(ID,L,W,H,Wt),
        linear(L,W,H,Lin),
        surcharge(Wt,Lin,Sur),
        base_fee(N,Base),
        Cost is Base + Sur.

/* --------------------------- Totals --------------------------------------- */

%  Total cost of every checked piece
total_checked_bags_cost(Total) :-
        findall(C, checked_bag_cost(_,C), Cs),
        sum_list(Cs, Total).

%  Ticket price
ticket_price(369).

%  Grand total: ticket + baggage
total_cost(Grand) :-
        total_checked_bags_cost(Bags),
        ticket_price(T),
        Grand is Bags + T.

/* --------------------------- Query ---------------------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.