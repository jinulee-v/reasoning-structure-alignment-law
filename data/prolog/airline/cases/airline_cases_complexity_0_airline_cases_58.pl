/* ------------  Rules from the statutes (abridged to what is relevant here) ------------ */

/* flight region */
within_us.   /* San Francisco - New Orleans */

/* passenger class */
class(main_plus).

/* how many free checked bags does this passenger get?              */
/* Main Plus = Main Cabin allowance (0 on purely domestic flights)   */
/*              + 1 extra free bag                                   */
free_checked_bags(1).

/* base checked-bag fees for flights wholly within the U.S.          */
/* (position in the sequence of checked bags -> fee in USD)          */
within_us_base_fee(1,40).
within_us_base_fee(2,45).
within_us_base_fee(3,150).
within_us_base_fee(4,200).
within_us_base_fee(Pos,200) :- Pos>=5.

/* oversize fee (sum of the 3 outside dimensions) - within U.S. */
oversize_fee(Size,0)                    :- Size =< 62.
oversize_fee(Size,30)                   :- Size  > 62, Size =< 65.
oversize_fee(Size,200)                  :- Size  > 65, Size =< 115.

/* overweight fee - within U.S. (lbs) */
overweight_fee(W,0)                     :- W =< 50.
overweight_fee(W,30)                    :- W  > 50, W =< 53.
overweight_fee(W,100)                   :- W  > 53, W =< 70.
overweight_fee(W,200)                   :- W  > 70, W =< 100.

/* for any bag the applicable extra fee is the higher of oversize vs. overweight */
extra_fee(BagId,Fee) :-
    bag(BagId,L,W,H,Weight),
    Size is L+W+H,
    oversize_fee(Size,OS),
    overweight_fee(Weight,OW),
    (OW >= OS -> Fee = OW ; Fee = OS).

/* --------------------  Facts from the case  -------------------- */

/* flight ticket price */
ticket_cost(208).

/* items the passenger brings (only those that must be checked) */
bag(bag2,37,17,11,97).   /* luggage box                           */
bag(bag3,35,15,13,51).   /* backpack                              */
bag(bag4,50,28,28,69).   /* backpack                              */
bag(bag5,53,30,26,53).   /* backpack                              */

/* list of checked bags in the order they will be processed */
checked_bags([bag2,bag3,bag4,bag5]).

/* --------------------  Computations  -------------------- */

/* sum of extra (oversize / overweight) fees */
extra_fees_sum([],0).
extra_fees_sum([B|T],Sum) :-
    extra_fee(B,F1),
    extra_fees_sum(T,FRest),
    Sum is F1 + FRest.

/* sum of base checked-bag fees taking into account free allowance */
base_fees_sum(Bags,Sum) :- free_checked_bags(Free),
                           base_fees_sum(Bags,1,Free,Sum).

base_fees_sum([],_,_,0).
base_fees_sum([_|T],Pos,Free,Sum) :-
    Pos =< Free,                      /* this bag is free */
    Pos1 is Pos + 1,
    base_fees_sum(T,Pos1,Free,Sum).
base_fees_sum([_|T],Pos,Free,Sum) :-
    Pos  > Free,                      /* fee applies      */
    within_us_base_fee(Pos,Fee),
    Pos1 is Pos + 1,
    base_fees_sum(T,Pos1,Free,Rest),
    Sum is Fee + Rest.

/* total bag fees */
total_bag_fees(Total) :-
    checked_bags(Bags),
    base_fees_sum(Bags,Base),
    extra_fees_sum(Bags,Extra),
    Total is Base + Extra.

/* overall cost (ticket + all bag related charges) */
total_cost(Total) :-
    ticket_cost(Ticket),
    total_bag_fees(Bags),
    Total is Ticket + Bags.

/* --------------------  Query / Output  -------------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.