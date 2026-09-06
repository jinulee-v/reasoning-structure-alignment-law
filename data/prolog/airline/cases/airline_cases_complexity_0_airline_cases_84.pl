/* -------------- RULES (statutes simplified to fit the case) -------------- */

/* route and service class that apply to Joseph */
route(india_to_us).                 /* New-Delhi (India) -> San-Francisco (U.S.) */
service_class(main_cabin).

/* ----  Carry-on rules  ---- */
carry_on_max(22,14,9).              /* in inches (L,W,H)      */

/* ----  Base checked-bag fees for Main-Cabin on India<->US route  ----
   BagNr = 1,2,3,4...  */
base_fee(1, 0).                      /* first bag is free (complimentary) */
base_fee(2,100).                     /* second bag               */
base_fee(3,200).                     /* third bag                */
base_fee(N,200):- N>=4.              /* fourth bag and beyond    */

/* ----  Oversize fees (bag length+width+height)  ---- */
oversize_fee(Sum,30) :- Sum>62 , Sum=<65.              /* 62-65 in  */
oversize_fee(Sum,200):- Sum>65 , Sum=<115.             /* 65-115 in */

/* ----  Over-weight fees (Joseph has no bag >70 lb, so only two brackets needed) */
overweight_fee(W,0  ) :- W=<50.                        /* not overweight */
overweight_fee(W,30 ) :- W>50 , W=<53.                 /* 50-53 lb bracket */
overweight_fee(W,100):- W>53 , W=<70.                  /* 53-70 lb bracket */

/* ----  Combined size / weight rule  ----
   If a bag is both oversize and overweight, charge ONLY the higher of the two. */
special_fee(Weight,Sum,Fee):-
    overweight_fee(Weight,OWF),
    oversize_fee(Sum,OSF), !,
    Fee is max(OWF,OSF).
special_fee(Weight,_,Fee):-                            /* only overweight */
    overweight_fee(Weight,Fee), Fee>0.
special_fee(_,Sum,Fee):-                               /* only oversize   */
    oversize_fee(Sum,Fee), Fee>0.
special_fee(_,_,0).                                   /* no extra fee    */

/* -------------- FACTS FROM JOSEPH'S CASE -------------- */

/* bag(Id, Length, Width, Height, Weight) */
bag(1,22,12, 9,  7).   /* will be the carry-on */
bag(2,34,21,10, 53).
bag(3,52,31,29, 51).
bag(4,34,20, 9, 53).
bag(5,48,37,24, 53).

/* -------------- DERIVED INFORMATION -------------- */

/* test whether a bag is carry-on size */
is_carry_on(Id):- bag(Id,L,W,H,_), carry_on_max(ML,MW,MH),
                  L=<ML, W=<MW, H=<MH.

/* make an ordered list of checked bags (all bags that are NOT carry-on) */
checked_bag_list(List):- findall(Id,(bag(Id,_,_,_,_), \+ is_carry_on(Id)),List).

/* fee for one checked bag in position N of the checked list */
checked_bag_fee(Id,N,TotalFee):-
    bag(Id,L,W,H,Weight),
    Sum is L+W+H,
    base_fee(N,Base),                       /* base fee by sequence number   */
    special_fee(Weight,Sum,SpecFee),        /* overweight / oversize fee      */
    TotalFee is Base + SpecFee.

/* sum of all checked-bag fees */
total_checked_fees(Sum):- checked_bag_list(List),
    findall(Fee,
            (nth1(N,List,Id), checked_bag_fee(Id,N,Fee)),
            Fees),
    sum_list(Fees,Sum).

/* flight ticket price (given) */
ticket_price(628).

/* total cost = ticket + checked bag fees (no special-needs costs in this case) */
total_cost(Total):- ticket_price(T),
                    total_checked_fees(BagFees),
                    Total is T + BagFees.

/* -------------- QUERY -------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.