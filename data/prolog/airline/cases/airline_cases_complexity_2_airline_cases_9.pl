/* --------------------  Rules from the statutes (only those needed) -------------------- */

/* overweight_fee(+Weight, -Fee)  --  flights to / from India              */
overweight_fee(W, 0   ) :- W =< 50, !.                /* not overweight */
overweight_fee(W, 30  ) :- W  > 50, W =< 53, !.
overweight_fee(W, 100 ) :- W  > 53, W =< 70, !.
overweight_fee(W, 450 ) :- W  > 70, W =< 100, !.

/* oversize_fee(+SizeSum, -Fee)   --  flights to / from India              */
oversize_fee(S, 0   ) :- S =< 62, !.                  /* within limit   */
oversize_fee(S, 30  ) :- S  > 62, S =< 65, !.
oversize_fee(S, 200 ) :- S  > 65, S =< 115, !.

/* extra_fee(+Weight,+SizeSum,-Fee) -- higher of overweight / oversize     */
extra_fee(W,S,Fee) :- overweight_fee(W,OW),
                      oversize_fee(S,OS),
                      (OW >= OS -> Fee = OW ; Fee = OS).

/* base_bag_fee(+Index, -Fee) -- premium-economy, to / from India          */
base_bag_fee(I, 0  ) :- I =< 2, !.         /* 1st & 2nd checked bags free  */
base_bag_fee(_, 200).

/* --------------------  Facts from Jennifer's case --------------------   */
/* bag(No, Weight(lbs), L,W,H inches) - Bag #1 is her carry-on and ignored */

bag(2, 84, 34,19,12).
bag(3, 55, 38,15,12).
bag(4, 83, 38,11,14).
bag(5, 54, 38,13,12).
bag(6, 58, 35,17,12).
bag(7, 51, 51,29,29).
bag(8, 61, 35,20,12).
bag(9, 53, 37,20,17).
bag(10,81, 36,14,13).
bag(11,84, 35,20,10).

flight_ticket_price(550).

/* --------------------  Helper predicates  ------------------------------ */

/* size_sum(+L,+W,+H,-Sum) */
size_sum(L,W,H,S) :- S is L+W+H.

/* bag_extra(+No,-ExtraFee)  - just the extra fee (over/over) for a bag    */
bag_extra(N,Fee) :- bag(N,W,L,B,H),
                    size_sum(L,B,H,S),
                    extra_fee(W,S,Fee).

/* list of all checked bag numbers (2 ... 11) */
checked_bag_numbers(Bags) :- findall(N, bag(N,_,_,_,_), Bags).

/* pick the two bags with the smallest extra fees to become the 1st & 2nd  */
first_two_free(First,Second) :-
    checked_bag_numbers(Ns),
    findall(F-N, (member(N,Ns), bag_extra(N,F)), Pairs),
    keysort(Pairs, Sorted),            /* ascending by F                   */
    Sorted = [ _-First, _-Second | _ ].

/* bag_index(+First,+Second,+BagNo,-Index)   (1-based among checked bags)  */
bag_index(F1,F2,No,Idx) :-
    checked_bag_numbers(All),
    exclude(==(F1), All, R1),
    exclude(==(F2), R1,  Rest),
    append([F1,F2], Rest, Ordered),    /* put chosen free bags first       */
    nth1(Idx, Ordered, No).

/* bag_total_cost(+First,+Second,+BagNo,-Cost) */
bag_total_cost(F1,F2,N,Cost) :-
    bag_index(F1,F2,N,Idx),
    base_bag_fee(Idx,BF),
    bag_extra(N,EF),
    Cost is BF + EF.

/* total_bags_cost(-Sum) -- sum over all checked bags                      */
total_bags_cost(Sum) :-
    first_two_free(F1,F2),
    checked_bag_numbers(Ns),
    findall(C, (member(N,Ns), bag_total_cost(F1,F2,N,C)), Cs),
    sum_list(Cs, Sum).

/* --------------------  Final result  ----------------------------------- */
total_cost(Total) :-
    flight_ticket_price(Tix),
    total_bags_cost(Bags),
    Total is Tix + Bags.

/* --------------------  Query  ------------------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.