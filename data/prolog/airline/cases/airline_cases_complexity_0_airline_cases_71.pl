/* ----------  Statutory rules that apply to this case  ---------- */

/* Base checked-bag fee for a Main Cabin customer travelling
   wholly within the U.S. (Houston - Miami) */
base_fee(1, 40).
base_fee(2, 45).
base_fee(3, 150).
base_fee(N, 200) :- N >= 4.

/* Oversize fees (U.S. / Canada / PR / USVI)                     */
oversize_fee(Size, 0)   :- Size =< 62.
oversize_fee(Size, 30)  :- Size  > 62, Size =< 65.
oversize_fee(Size, 200) :- Size  > 65.

/* Over-weight fees (U.S. / Canada / PR / USVI)                  */
overweight_fee(W, 0)   :- W =< 50.
overweight_fee(W, 30)  :- W  > 50, W =< 53.
overweight_fee(W, 100) :- W  > 53, W =< 70.
overweight_fee(W, 200) :- W  > 70, W =< 100.

/* The surcharge for a bag is the higher of the oversize or
   overweight fee (if both are non-zero).                        */
surcharge(Size, W, S) :-
    oversize_fee(Size, OS),
    overweight_fee(W,  OW),
    (OS >= OW -> S = OS ; S = OW).

/* ----------------  Facts describing the passenger  ------------ */

ticket_price(285).          /* Flight price                          */
class(main_cabin).          /* Fare class                            */
route(within_us).           /* Houston - Miami                       */

/* Bag(id, Length, Width, Height, Weight).                          */
bag(1, 19, 11,  7, 12).   /* this is a free carry-on                */
bag(2, 42, 26, 23, 53).
bag(3, 36, 18, 11, 51).
bag(4, 44, 29, 24, 65).
bag(5, 39, 22, 18, 52).

/* ----------  Rules to decide which bags are checked  ----------- */

/* A bag is a free carry-on if it meets the 22*14*9 limits.        */
carry_on(ID) :-
    bag(ID, L, W, H, _),
    L =< 22, W =< 14, H =< 9.

/* All other bags must be checked.                                 */
checked_bag(ID) :-
    bag(ID, _, _, _, _),
    \+ carry_on(ID).

/* Produce the list of checked bags in ascending bag-ID order.     */
checked_bag_list(List) :-
    findall(ID, checked_bag(ID), Raw),
    sort(Raw, List).

/* -----------------  Fee calculation per bag  ------------------- */

bag_base_fee(Seq, Fee) :- base_fee(Seq, Fee).

bag_surcharge(ID, Surcharge) :-
    bag(ID, L, W, H, Weight),
    Size is L + W + H,
    surcharge(Size, Weight, Surcharge).

bag_total_fee(Seq, ID, Total) :-
    bag_base_fee(Seq, Base),
    bag_surcharge(ID, Extra),
    Total is Base + Extra.

/* -------------  Sum of all checked-bag fees  ------------------- */

total_bag_fees(Total) :-
    checked_bag_list(List),
    findall(F,
            (nth1(Seq, List, ID), bag_total_fee(Seq, ID, F)),
            Fees),
    sumlist(Fees, Total).

/* ----------------------  Grand total  -------------------------- */

total_cost(Total) :-
    ticket_price(Tix),
    total_bag_fees(Bags),
    Total is Tix + Bags.

/* --------------------------  Query  ---------------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.