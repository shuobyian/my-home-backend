import { Product } from 'src/product/entities/product.entity';
import {
  Column,
  CreateDateColumn,
  Entity,
  JoinColumn,
  OneToOne,
  PrimaryGeneratedColumn,
  UpdateDateColumn,
} from 'typeorm';

@Entity('result', { schema: 'public' })
export class Result {
  @PrimaryGeneratedColumn({ type: 'integer', name: 'id' })
  id: number;

  @CreateDateColumn({
    type: 'timestamp with time zone',
    name: 'createdAt',
    default: () => 'CURRENT_TIMESTAMP',
  })
  createdAt: string;

  @UpdateDateColumn({
    type: 'timestamp with time zone',
    name: 'updatedAt',
    nullable: true,
  })
  updatedAt: string | null;

  @Column('integer', { name: 'product_id' })
  product_id: number;

  @Column('varchar', { name: 'names' })
  names: string;

  @Column('varchar', { name: 'counts' })
  counts: string;

  @Column('varchar', { name: 'prices' })
  prices: string;

  @Column('integer', { name: 'totalPrice' })
  totalPrice: number;

  @OneToOne(() => Product, (product) => product)
  @JoinColumn([{ name: 'product_id', referencedColumnName: 'id' }])
  product: Product;
}
